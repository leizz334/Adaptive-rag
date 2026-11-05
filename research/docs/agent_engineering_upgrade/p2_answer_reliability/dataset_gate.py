"""Aggregate-only quality gate; do not print holdout inputs, Gold or outcomes."""

import hashlib
import json

from eval.answer_scoring import AnswerGold
from eval.multiturn import load_scenarios
from research.docs.agent_engineering_upgrade.p2_answer_reliability.manage import HERE, save


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_dataset(path, answer_path):
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    assert "\ufffd" not in text and "\ufffd" not in answer_path.read_text(encoding="utf-8")
    cases, digest = load_scenarios(path)
    assert len(cases) >= 20
    labels = json.loads(answer_path.read_bytes())
    assert set(labels) == {c.id for c in cases}
    for case in cases:
        assert len(labels[case.id]) == len(case.turns)
        for turn, gold in zip(case.turns, labels[case.id], strict=True):
            assert any("\u4e00" <= c <= "\u9fff" for c in turn.message)
            assert not set(turn.message.strip()) <= set("?？ .")
            spec = AnswerGold.model_validate(gold)
            assert not any(
                p in {".*", ".+", "[\\s\\S]*", "^.*$"} for p in spec.allowed_extra_patterns
            )
            assert all(g in spec.subgoals for g in (f.goal for f in spec.facts))
    return cases, dict(
        cases=len(cases),
        turns=sum(len(c.turns) for c in cases),
        facts=sum(len(g["facts"]) for gs in labels.values() for g in gs),
        semantic_required=sum(
            g.get("semantic_required", True) for gs in labels.values() for g in gs
        ),
        scenario_sha256=digest,
        answer_sha256=sha(answer_path),
        utf8=True,
        strict_schema=True,
        agent_run=False,
    )


def main():
    data = HERE / "datasets"
    dev, devmeta = check_dataset(data / "development.json", data / "development_answers.json")
    held, heldmeta = check_dataset(data / "holdout.json", data / "holdout_answers.json")

    # Shared tiny supporting turns are reported, not secretly changed. Exact full
    # scenarios and terminal-task utterances must be distinct.
    def signature(c):
        return json.dumps(
            [t.model_dump(mode="json") for t in c.turns], sort_keys=True, ensure_ascii=False
        )

    assert not {signature(c) for c in dev} & {signature(c) for c in held}
    shared = {c.turns[-1].message for c in dev} & {c.turns[-1].message for c in held}
    assert not shared, "Terminal task overlap; report and resolve before evaluation"
    value = dict(
        status="PASS",
        development=devmeta,
        holdout=heldmeta,
        exact_scenario_overlap=0,
        terminal_task_overlap=0,
        gold_to_agent=False,
        holdout_content_printed=False,
        holdout_outcomes="NOT_RUN",
        independent_author_procedural_isolation=True,
        human_semantic_calibration="NOT_RUN",
        fault_coverage="Separate unit/replay fault matrix; ordinary scenario driver has no fault field",
    )
    save(HERE / "evidence/s4_dataset_quality.json", value)
    print(json.dumps(value))


if __name__ == "__main__":
    main()
