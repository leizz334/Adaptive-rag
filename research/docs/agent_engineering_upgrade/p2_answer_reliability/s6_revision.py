"""Freeze a versioned evaluator revision without changing earlier evidence."""

import hashlib
import json
from datetime import UTC, datetime

from research.docs.agent_engineering_upgrade.p2_answer_reliability.dataset_gate import check_dataset
from research.docs.agent_engineering_upgrade.p2_answer_reliability.manage import HERE, ROOT, save


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = HERE / "evidence/candidate_freeze_v21.json"
    assert not target.exists(), "A freeze is immutable; use a new revision"
    original = json.loads((HERE / "evidence/candidate_freeze.json").read_bytes())
    assert original["app_hashes"] == {
        p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / "app").rglob("*.py")
    }
    data = HERE / "datasets"
    manifest = json.loads((data / "validation_holdout_v21_manifest.json").read_bytes())
    for name, expected in manifest["frozen_sha256"].items():
        assert sha(data / name) == expected
    _, quality = check_dataset(
        data / "validation_holdout_v21.json", data / "validation_holdout_v21_answers.json"
    )
    assert quality["cases"] == 24 and quality["turns"] == 26
    assert all(sha(data / name) == value for name, value in original["datasets"].items())
    value = dict(original)
    value.update(
        frozen_at=datetime.now(UTC).isoformat(),
        scorer_sha256=sha(ROOT / "eval/answer_scoring.py"),
        scorer_version="answer-eval-v2.1",
        datasets={p.name: sha(p) for p in data.glob("*.json")},
        previous_freeze_sha256=sha(HERE / "evidence/candidate_freeze.json"),
        reason="Development real pilot exposed an entity-association false negative; V20 retained",
        app_changes_after_original_holdout=False,
        original_holdout_status="CONSUMED_REGRESSION_ONLY",
        fresh_validation_isolation="Independent author; procedural, not cryptographic; no implementation runs before this freeze",
        independent_author_timing="Data authored while evaluator review was pending; final scorer corrections frozen before execution; no data tuning",
        semantic_human_calibration="NOT_RUN",
    )
    save(target, value)
    save(HERE / "evidence/s6_v21_dataset_gate.json", quality)
    run = HERE / "runs/20261105_S6_pairs_02"
    save(
        run / "validation.json",
        dict(
            status="PARTIAL_SCORER_CONTRACT_STOP",
            completed_pairs=1,
            requests=11,
            reported_tokens=10003,
            paid_replay=False,
            raw_results_preserved=True,
            stop_reason="Quantity before SKU was misclassified as missing by V20; new evaluator revision required",
            raw_artifact_sha256={
                n: sha(run / n) for n in ("experiment_config.json", "requests.json", "results.json")
            },
        ),
    )
    print(json.dumps(dict(freeze_sha256=sha(target), validation_quality=quality)))


if __name__ == "__main__":
    main()
