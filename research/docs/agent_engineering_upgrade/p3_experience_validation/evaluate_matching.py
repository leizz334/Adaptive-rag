"""Frozen relevance comparison; no Agent retrieval, injection, model or writes."""

import json
from datetime import UTC, datetime

from app.experience.applicability import ApplicabilityTask, matches_offline
from app.experience.contracts import EvidenceRef
from app.experience.reflection import ExperienceCandidate
from app.experience.review_applicability import BASE_GUARDS, ReviewContext, review_applicability
from app.experience.shadow import EvidenceResolver
from research.docs.agent_engineering_upgrade.p3_experience_validation.manage import (
    BASE,
    HERE,
    ROOT,
    git,
    save,
    sha,
)

NOW = datetime(2026, 11, 9, tzinfo=UTC)
FAMILIES = ("mixed_evidence", "judge_output", "fallback_evidence")
PRIOR = HERE.parent / "p3_experience_shadow"
CANDIDATES = PRIOR / "runs/20261109_shadow_01/experience_candidates.json"
HOLDOUT_HASHES = {
    "blind_holdout.json": "f53bbd6bda1d4977b4b96eee09f4043ea5e3bee78ae147ae3e60f5032bd9348d",
    "blind_gold.json": "9284ff115dd69685dbb826d3fd86f24279f3e2376726b87ac7b28c4e844e4132",
}


def read(path):
    return json.loads(path.read_bytes())


def implementation_hashes():
    paths = [
        ROOT / "app/experience/review_applicability.py",
        ROOT / "app/experience/applicability.py",
        ROOT / "app/experience/reflection.py",
        ROOT / "app/experience/contracts.py",
        ROOT / "app/experience/shadow.py",
        HERE / "evaluate_matching.py",
    ]
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def freeze():
    target = HERE / "evidence/b0_freeze.json"
    assert not target.exists(), "Frozen source/data cannot be overwritten"
    for name, digest in HOLDOUT_HASHES.items():
        assert sha(HERE / "datasets" / name) == digest
    old = git("show", f"{BASE}:app/experience/applicability.py").encode() + b"\n"
    assert old == (ROOT / "app/experience/applicability.py").read_bytes()
    (HERE / "evidence/c0_applicability.py.txt").write_bytes(old)
    save(
        target,
        dict(
            schema_version="p3b-review-comparison-v1",
            source_head=git("rev-parse", "HEAD"),
            clock=NOW.isoformat(),
            sources=implementation_hashes(),
            datasets={p.name: sha(p) for p in (HERE / "datasets").glob("*.json")},
            candidate_export_sha256=sha(CANDIDATES),
            C0="Unchanged v1 restrictive matcher",
            C1="Versioned source-bound principle review with explicit NO_EXECUTION/NO_INJECTION and inherited execution restrictions",
            comparison_scope="Relevance Gold unchanged; this is not an authorization, retrieval, injection or benefit test",
            human_calibration="NOT_RUN",
            new_http=0,
        ),
    )
    print("Implementation/scorer/data frozen before concrete blind evaluation")


def project_input(row, candidate):
    scope = candidate.scope
    condition = row["scope_condition"]
    if condition != "same":
        field = {
            "other_user": "user_ref",
            "other_tenant": "tenant_ref",
            "other_session": "session_ref",
            "unverified": "verified",
        }[condition]
        scope = scope.model_copy(update={field: False if condition == "unverified" else "d" * 64})
    state = row["lesson_state"]
    if state in {"expired", "rejected"}:
        candidate = candidate.model_copy(update={"validation_status": state.upper()})
    elif state == "human_rejected":
        candidate = candidate.model_copy(update={"review_status": "HUMAN_REJECTED"})
    source = candidate.source_version if row["version_relation"] == "same" else "f" * 40
    return candidate, ApplicabilityTask(
        scope=scope, tags=row["features"]["tags"], source_version=source
    )


def summarize(rows):
    tp = sum(r["match"] and r["expected"] for r in rows)
    fp = sum(r["match"] and not r["expected"] for r in rows)
    fn = sum(not r["match"] and r["expected"] for r in rows)
    tn = sum(not r["match"] and not r["expected"] for r in rows)
    return dict(
        TP=tp,
        FP=fp,
        FN=fn,
        TN=tn,
        precision=tp / (tp + fp) if tp + fp else None,
        recall=tp / (tp + fn) if tp + fn else None,
        safety_conflicts=sum(r["safety_conflict"] for r in rows),
        missing_required_guard_decisions=sum(bool(r["missing_guards"]) for r in rows),
        strict_validation_pass=all(
            r["match"] == r["expected"] and not r["safety_conflict"] and not r["missing_guards"]
            for r in rows
        ),
    )


def run(output):
    frozen = read(HERE / "evidence/b0_freeze.json")
    assert frozen["sources"] == implementation_hashes()
    assert frozen["candidate_export_sha256"] == sha(CANDIDATES)
    assert all(sha(HERE / "datasets" / name) == h for name, h in frozen["datasets"].items())
    output.mkdir(parents=True, exist_ok=False)
    candidates = [ExperienceCandidate.model_validate(x) for x in read(CANDIDATES)]
    resolver = EvidenceResolver(ROOT)
    for candidate in candidates:
        for reference in candidate.evidence_refs:
            resolver.resolve(reference)
    save(
        output / "experiment_config.json",
        dict(
            freeze_sha256=sha(HERE / "evidence/b0_freeze.json"),
            clock=NOW.isoformat(),
            source_head=git("rev-parse", "HEAD"),
            candidate_fingerprints={c.family: c.fingerprint for c in candidates},
            candidate_state="All original NEEDS_REVIEW/UNREVIEWED; no state changes",
            new_http=0,
            new_tokens=0,
            injection_run=False,
            production_active=False,
        ),
    )
    summaries = {}
    diagnoses = []
    for cohort in ("consumed_diagnostics", "development", "blind_holdout"):
        inputs = HERE / "datasets" / f"{cohort}.json"
        gold_name = "blind_gold.json" if cohort == "blind_holdout" else f"{cohort}_gold.json"
        data = read(inputs)
        input_by_id = {row["id"]: row for row in data["cases"]}
        predictions = []
        for index, row in enumerate(data["cases"]):
            for original in candidates:
                candidate, task = project_input(row, original)
                c0 = matches_offline(candidate, task, now=NOW)
                reference = EvidenceRef(
                    artifact=inputs.relative_to(ROOT).as_posix(),
                    sha256=sha(inputs),
                    pointer=f"/cases/{index}/features",
                    kind="evaluation",
                )
                context = ReviewContext(task=task, features=row["features"], features_ref=reference)
                c1 = review_applicability(candidate, context, resolver=resolver, now=NOW)
                predictions.append(
                    dict(
                        case_id=row["id"],
                        family=original.family,
                        C0=c0,
                        C1=c1.model_dump(mode="json"),
                    )
                )
        # Gold is loaded only after every prediction in this cohort exists.
        gold = read(HERE / "datasets" / gold_name)["cases"]
        scored = []
        for row in predictions:
            label = gold[row["case_id"]]
            expected = row["family"] in label["expected_families"]
            for arm in ("C0", "C1"):
                matched = row[arm] if arm == "C0" else row[arm]["status"] == "MATCH_FOR_REVIEW"
                decision = row["C1"]
                source_input = input_by_id[row["case_id"]]
                missing = (
                    sorted(
                        set(label.get("required_guards", {}).get(row["family"], []))
                        - set(decision["guards"])
                    )
                    if arm == "C1" and matched
                    else []
                )
                conflict = arm == "C1" and (
                    decision["execution_permitted"]
                    or decision["injection_permitted"]
                    or decision["human_approval_granted"]
                    or not set(BASE_GUARDS) <= set(decision["guards"])
                    or (
                        matched
                        and (
                            source_input["scope_condition"] != "same"
                            or source_input["lesson_state"]
                            in {"expired", "rejected", "human_rejected"}
                            or source_input["version_relation"] != "same"
                            or not source_input["features"]["annotation_verified"]
                            or bool(missing)
                        )
                    )
                )
                scored.append(
                    dict(
                        case_id=row["case_id"],
                        family=row["family"],
                        arm=arm,
                        match=matched,
                        expected=expected,
                        safety_conflict=bool(conflict),
                        missing_guards=missing,
                    )
                )
            if cohort == "consumed_diagnostics" and expected and not row["C0"]:
                original = next(c for c in candidates if c.family == row["family"])
                source = next(x for x in data["cases"] if x["id"] == row["case_id"])
                tags = set(source["features"]["tags"])
                diagnoses.append(
                    dict(
                        case_id=row["case_id"],
                        family=row["family"],
                        query=source["task_summary"],
                        missing_positive=sorted(set(original.applicability_conditions) - tags),
                        excluded_contexts=sorted(set(original.non_applicability_conditions) & tags),
                        root="v1boolean combines principle relevance with blanket risk exclusion/available-evidence precondition",
                        new_decision=row["C1"],
                        original_gold_changed=False,
                    )
                )
        save(output / f"{cohort}_predictions.json", predictions)
        save(output / f"{cohort}_scores.json", scored)
        summaries[cohort] = dict(
            cases=len(data["cases"]),
            arms={arm: summarize([r for r in scored if r["arm"] == arm]) for arm in ("C0", "C1")},
            families={
                family: {
                    arm: summarize([r for r in scored if r["arm"] == arm and r["family"] == family])
                    for arm in ("C0", "C1")
                }
                for family in FAMILIES
            },
            negative_matching_transitions=sum(
                r["C0"] and r["C1"]["status"] != "MATCH_FOR_REVIEW" for r in predictions
            ),
            positive_matching_transitions=sum(
                not r["C0"] and r["C1"]["status"] == "MATCH_FOR_REVIEW" for r in predictions
            ),
        )
    baseline = summaries["consumed_diagnostics"]["arms"]["C0"]
    assert (baseline["TP"], baseline["FP"], baseline["FN"], baseline["TN"]) == (12, 0, 8, 76)
    assert implementation_hashes() == frozen["sources"]
    assert all(sha(HERE / "datasets" / name) == h for name, h in frozen["datasets"].items())
    result = dict(
        status="COMPLETED",
        cohorts=summaries,
        strict_blind_applicability_contracts_passed=sum(
            summaries["blind_holdout"]["families"][f]["C1"]["strict_validation_pass"]
            for f in FAMILIES
        ),
        approved_experiences=0,
        human_calibration="NOT_RUN",
        experience_benefit="NOT_ESTABLISHED",
        agent_negative_transfer="NOT_RUN_WAIT_HUMAN",
        original_candidate_states_unchanged=True,
        new_http=0,
        new_tokens=0,
        active_enabled=False,
    )
    save(output / "results.json", result)
    save(output / "eight_misses.json", dict(count=len(diagnoses), cases=diagnoses))
    save(
        output / "validation.json",
        dict(
            source_and_gold_unchanged=True,
            blind_consumed_only_after_freeze=True,
            C0_raw_baseline_reproduced=True,
            no_injection_or_authorization=True,
            human_gate_pending=True,
        ),
    )
    print(
        json.dumps(
            dict(
                cohorts={k: v["arms"] for k, v in summaries.items()},
                strict_blind_applicability_contracts_passed=result[
                    "strict_blind_applicability_contracts_passed"
                ],
                approved_experiences=0,
            )
        )
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "run"])
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.command == "freeze":
        freeze()
    else:
        from pathlib import Path

        if not args.output:
            parser.error("New --output required")
        run(Path(args.output).resolve())
