"""Offline source-response replay and private shadow applicability evaluation.

No .env access, live transport or production database. Gold is read only by E2
after candidate generation has completed and implementation hashes are frozen.
"""

import asyncio
import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from app.config.settings import Settings
from app.experience.applicability import ApplicabilityTask, matches_offline
from app.experience.contracts import EvidenceRef, ExperienceScope, FailureAssessment
from app.experience.reflection import reflect
from app.experience.shadow import EvidenceResolver, ShadowObserver
from app.experience.storage import ExperienceRepository, initialize_schema
from app.experience.taxonomy import classify_failure
from app.repositories.db import create_engine, create_session_factory
from eval.multiturn import load_scenarios
from research.docs.agent_engineering_upgrade.p2_agent_quality.replay_paid import ReplayLLM
from research.docs.agent_engineering_upgrade.p2_answer_reliability.real_pairs import capture_case
from research.docs.agent_engineering_upgrade.p3_experience_shadow.manage import (
    BASE,
    HERE,
    ROOT,
    git,
    save,
    sha,
)

NOW = datetime(2026, 11, 9, tzinfo=UTC)
P2 = HERE.parent / "p2_answer_reliability"
HOLDOUT = HERE / "evaluation/applicability_holdout.json"
EXPECTED_HOLDOUT_SHA = "e4359ee34c69f8874b9fe91c8fa5e116b0ea39802efac903be5ca70797225cff"


def read(path):
    return json.loads(path.read_bytes())


def identity():
    def digest(text):
        return hashlib.sha256(text.encode()).hexdigest()

    return ExperienceScope(
        tenant_ref=digest("isolated-synthetic-analysis"),
        user_ref=digest("offline-review-operator"),
        session_ref=digest("p3a-frozen-private-job"),
        verified=True,
    )


def source_hashes():
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / "app/experience").glob("*.py")}


def freeze():
    target = HERE / "evidence/a5_implementation_freeze.json"
    if target.exists():
        raise ValueError("Implementation freeze is immutable")
    assert sha(HOLDOUT) == EXPECTED_HOLDOUT_SHA
    old = read(HERE / "evidence/preservation.json")
    assert all(
        sha(ROOT / p) == h for p, h in old["prior_files"].items() if p.startswith(("app/", "eval/"))
    )
    save(
        target,
        dict(
            source_commit=git("rev-parse", "HEAD"),
            app_experience=source_hashes(),
            runner_sha256=sha(Path(__file__)),
            holdout_sha256=EXPECTED_HOLDOUT_SHA,
            holdout_manifest_sha256=sha(HERE / "evaluation/applicability_manifest.json"),
            clock=NOW.isoformat(),
            candidate_origin="Fixed generic catalog plus independently reviewed development failures; no validation labels used",
            new_paid_requests=0,
            old_business_source_unchanged=True,
            active_enabled=False,
        ),
    )
    print("Implementation/scorer frozen before E2 input/Gold evaluation")


def canonical(capture):
    trace = capture["traces"][0]
    decisions = []
    for turn in trace["turns"]:
        response = turn.get("response") or {}
        decisions.append(
            dict(
                answer=response.get("answer"),
                intent=response.get("intent"),
                strategy=response.get("strategy"),
                complexity=response.get("complexity"),
                pending=response.get("pending_action"),
                refused=response.get("refused"),
                nodes=[n["node"] for n in turn["nodes"]],
                plans=[n["output"].get("plan") for n in turn["nodes"] if n["node"] == "plan_tasks"],
            )
        )
    calls = [
        {
            k: c.get(k)
            for k in ("name", "arguments", "status", "success", "failure_kind", "output", "turn")
        }
        for c in capture["results"][0]["evidence"]["tool_calls"]
    ]
    return dict(
        decisions=decisions,
        tool_calls=calls,
        business_initial=trace["database_initial"]["business"],
        business_final=trace["database_final"]["business"],
    )


def ref_for(path, pointer, kind="trace"):
    return EvidenceRef(
        artifact=path.relative_to(ROOT).as_posix(), sha256=sha(path), pointer=pointer, kind=kind
    )


def reviewed_development_assessments():
    diagnoses = read(HERE / "evidence/a2_trace_diagnoses.json")
    normalized = read(HERE / "evidence/a3_context_assessments.json")["rows"]
    # Review-time context annotation, not a production case-ID routing rule.
    # Source routing cases in this cohort were independently diagnosed as mixed
    # product-description/current-price goals. Supplementary warranty cases are
    # not assigned these tags. No E2 validation input is read here.
    reviewed_context = {
        r["diagnosis_id"]: ["live_fact", "static_policy"]
        for r in diagnoses["p2s_real14"]
        if r.get("primary_category") == "ROUTING_ERROR"
    }
    result = []
    for item in normalized:
        data = item["assessment"]
        if data["source_trace_id"] in reviewed_context:
            data = data | dict(context_tags=reviewed_context[data["source_trace_id"]])
        result.append(
            dict(origin=item["cohort"], assessment=FailureAssessment.model_validate(data))
        )
    # Independently reviewed secondary errors stay separate events, not extra
    # population failures. All P2-R sources here are explicit offline replays.
    for row in diagnoses["p2r_supplementary"]:
        if "JUDGE_INVALID_OUTPUT" not in row.get("secondary_categories", []):
            continue
        refs = [
            EvidenceRef(
                artifact=diagnoses["source_registry"][r["source_id"]]["path"],
                sha256=diagnoses["source_registry"][r["source_id"]]["sha256"],
                pointer=r["json_pointer"],
                kind="trace",
            )
            for r in row["evidence_refs"]
        ]
        for category, tags in (
            ("JUDGE_INVALID_OUTPUT", ["judge_invalid", "evidence_available"]),
            ("FALLBACK_ERROR", ["fallback_needed", "evidence_available"]),
        ):
            # Fallback evidence is independently diagnosed only for goal loss;
            # no automatic conclusion is drawn for unavailable SKU facts.
            if category == "FALLBACK_ERROR" and row["primary_category"] != "GOAL_OMISSION":
                continue
            assessment = classify_failure(
                source_trace_id=row["diagnosis_id"] + ":" + category,
                source_case_id=row["case_id"],
                source_version=BASE,
                signals=[
                    dict(
                        category=category,
                        proof="TRACE_CONTRACT",
                        node="check_faithfulness",
                        position=6,
                        evidence_refs=refs,
                        context_tags=tags,
                        summary="Independently reviewed completed-response replay error",
                        root_cause_hypothesis="Structured Judge and fallback mechanism remains a separately qualified hypothesis",
                    )
                ],
            )
            result.append(
                dict(origin="P2R_SUPPLEMENTARY_OFFLINE_REPLAY_SECONDARY", assessment=assessment)
            )
    return result


async def evaluate(output):
    frozen = read(HERE / "evidence/a5_implementation_freeze.json")
    assert (
        frozen["app_experience"] == source_hashes()
        and frozen["runner_sha256"] == sha(Path(__file__))
        and sha(HOLDOUT) == frozen["holdout_sha256"]
    )
    output.mkdir(parents=True, exist_ok=False)
    save(
        output / "experiment_config.json",
        dict(
            schema="p3a-shadow-control-v1",
            source_commit=git("rev-parse", "HEAD"),
            freeze_sha256=sha(HERE / "evidence/a5_implementation_freeze.json"),
            clock=NOW.isoformat(),
            memory="M2",
            E0="Unmodified P2S business application; exact completed-response MockTransport replay",
            E1="Same application/replay plus isolated post-task shadow observer",
            E2="Frozen independent structured applicability annotations; no injection",
            http_limit=120,
            token_limit=120000,
            estimated_usd_limit=2,
            concurrency=1,
            new_http_requests=0,
            new_tokens=0,
            actual_new_cost_usd=0,
            pricing="NOT_APPLICABLE_NO_NEW_REQUESTS",
            historical_price_ref="p2_answer_reliability/P2-S6_REAL_LLM_REPORT.md; not a new verified rate",
            external_tracing=False,
        ),
    )
    db = output / "experience.sqlite3"
    engine = create_engine(
        Settings(
            _env_file=None, app_env="testing", database_url=f"sqlite+aiosqlite:///{db.as_posix()}"
        )
    )
    await initialize_schema(engine, isolated=True)
    repo = ExperienceRepository(
        create_session_factory(engine), resolver=EvidenceResolver(ROOT), clock=lambda: NOW
    )
    proposed = []

    async def sink(candidate):
        proposed.append(candidate)
        await repo.propose(identity(), candidate)

    observer = ShadowObserver(
        mode="shadow",
        resolver=EvidenceResolver(ROOT),
        sink=sink,
        max_observations=128,
        clock=lambda: NOW,
    )
    development = reviewed_development_assessments()
    assessment_map = {x["assessment"].source_trace_id: x["assessment"] for x in development}
    controls = []
    try:
        for run_name in ("20261105_S6_pairs_02", "20261108_S6_pairs_03"):
            run = P2 / "runs" / run_name
            config, results, requests = (
                read(run / "experiment_config.json"),
                read(run / "results.json"),
                read(run / "requests.json"),
            )
            snapshot = config["snapshots"]["R1"]
            settings = Settings(
                _env_file=None,
                app_env="testing",
                deepseek_api_key="synthetic-offline-replay-only",
                deepseek_base_url=snapshot["endpoint"],
                deepseek_model=snapshot["model"],
                llm_max_retries=1,
                agent_tracing_enabled=False,
            )
            for group in results["groups"]:
                if group["variant"] != "R1":
                    continue
                dataset = config["datasets"][group["split"]]
                cases, dataset_hash = load_scenarios(Path(dataset["path"]))
                case = next(c for c in cases if c.id == group["case_id"])
                rows = [r for r in requests if r["group"] == group["group"]]
                arms = {}
                for arm in ("E0", "E1"):
                    provider = ReplayLLM(settings, rows)
                    try:
                        captured = await capture_case(
                            case,
                            dataset_hash,
                            provider,
                            allow_real_network=False,
                            seed_clock=config["seed_clock"],
                        )
                        if provider.failure or provider.sequence != len(rows):
                            raise ValueError("Incomplete exact replay; never use a live fallback")
                        value = canonical(captured)
                        before = json.dumps(value, sort_keys=True, ensure_ascii=False)
                        outcome = None
                        if arm == "E1":
                            assessed = assessment_map[f"P2S-{case.id}-R1"]
                            # Reuse the same frozen clock for candidate TTL.
                            outcome = await observer.observe(
                                value, assessed, identity(), completed=True
                            )
                            if json.dumps(value, sort_keys=True, ensure_ascii=False) != before:
                                raise AssertionError("Shadow changed completed result")
                        arms[arm] = dict(
                            canonical=value,
                            replay_responses_consumed=provider.sequence,
                            observer=outcome.status if outcome else "OFF",
                        )
                        save(output / f"{case.id}_{arm}.json", arms[arm])
                    finally:
                        await provider.aclose()
                original = read(run / "captures" / (group["group"].replace(":", "_") + ".json"))
                controls.append(
                    dict(
                        case_id=case.id,
                        identical=arms["E0"]["canonical"] == arms["E1"]["canonical"],
                        same_as_saved_public_answer=arms["E0"]["canonical"]["decisions"][0][
                            "answer"
                        ]
                        == original["traces"][0]["turns"][0]["response"]["answer"],
                        new_http_requests=0,
                        consumed_responses=arms["E0"]["replay_responses_consumed"],
                    )
                )
        # Candidate generation precedes any independent applicability Gold load.
        for item in development:
            candidate = reflect(item["assessment"], identity(), now=NOW)
            if candidate:
                proposed.append(candidate)
                await repo.propose(identity(), candidate)
        candidates = await repo.list(identity())
        for candidate in candidates:
            if candidate.validation_status == "PROPOSED":
                await repo.transition(
                    identity(),
                    candidate.experience_id,
                    "NEEDS_REVIEW",
                    expected_version=candidate.version,
                )
        candidates = await repo.list(identity())
        save(output / "experience_candidates.json", [c.model_dump(mode="json") for c in candidates])
        # E2 is the first access to concrete independent cases/labels by this
        # implementation. Raw text is not used as instructions or an NLU score.
        data = read(HOLDOUT)
        evaluations = []
        for task in data["cases"]:
            scoped = identity()
            condition = task["scope_condition"]
            if condition != "same":
                field = {
                    "other_user": "user_ref",
                    "other_tenant": "tenant_ref",
                    "other_session": "session_ref",
                    "unverified": "verified",
                }[condition]
                scoped = scoped.model_copy(
                    update={field: False if condition == "unverified" else "d" * 64}
                )
            expected = set(task["expected_families"])
            for candidate in candidates:
                state = task["lesson_state"]
                tested = candidate
                if state in {"expired", "rejected"}:
                    tested = candidate.model_copy(update={"validation_status": state.upper()})
                descriptor = ApplicabilityTask(
                    scope=scoped, tags=task["tags"], source_version=candidate.source_version
                )
                actual = matches_offline(tested, descriptor, now=NOW)
                evaluations.append(
                    dict(
                        case_id=task["id"],
                        family=candidate.family,
                        expected=candidate.family in expected,
                        actual=actual,
                        match=actual == (candidate.family in expected),
                        safety_conflict=actual
                        and (condition != "same" or "untrusted_input" in task["tags"]),
                    )
                )
        verified = []
        for candidate in candidates:
            scoped = [r for r in evaluations if r["family"] == candidate.family]
            passed = all(r["match"] and not r["safety_conflict"] for r in scoped)
            evidence = dict(
                scope="offline_applicability",
                family=candidate.family,
                source_version=candidate.source_version,
                candidate_fingerprint=candidate.fingerprint,
                independent_labels=True,
                passed=passed,
                cases=len(scoped),
                safety_conflicts=sum(r["safety_conflict"] for r in scoped),
                dataset_sha256=sha(HOLDOUT),
                scope_limit="Structured applicability only; no injected Agent benefit or human approval",
            )
            path = output / f"validation_{candidate.family}.json"
            save(path, evidence)
            if passed:
                updated = await repo.transition(
                    identity(),
                    candidate.experience_id,
                    "VERIFIED_OFFLINE",
                    expected_version=candidate.version,
                    validation_evidence=ref_for(path, "", kind="evaluation"),
                )
                verified.append(updated.experience_id)
        tp = sum(r["actual"] and r["expected"] for r in evaluations)
        fp = sum(r["actual"] and not r["expected"] for r in evaluations)
        fn = sum(not r["actual"] and r["expected"] for r in evaluations)
        tn = sum(not r["actual"] and not r["expected"] for r in evaluations)
        result = dict(
            status="COMPLETED",
            E0_E1=dict(
                cases=len(controls),
                divergence=sum(not r["identical"] for r in controls),
                saved_public_answer_mismatches=sum(
                    not r["same_as_saved_public_answer"] for r in controls
                ),
                controls=controls,
            ),
            candidate_attempts=len(proposed),
            unique_candidates=len(candidates),
            duplicate_attempts=len(proposed) - len(candidates),
            verified_offline=len(verified),
            rejected=0,
            unresolved_candidates=len(candidates) - len(verified),
            validation_rate=len(verified) / len(candidates) if candidates else None,
            E2=dict(
                cases=len(data["cases"]),
                decisions=len(evaluations),
                TP=tp,
                FP=fp,
                FN=fn,
                TN=tn,
                false_applicability_rate=fp / (fp + tn) if fp + tn else None,
                safety_conflicts=sum(r["safety_conflict"] for r in evaluations),
                rows=evaluations,
            ),
            failure_classification_accuracy="NOT_ASSESSED_NO_BLIND_ROOT_CAUSE_LABELS",
            reflection_validity="EVIDENCE_GATED_CATALOG_MECHANISM_ONLY",
            experience_benefit="NOT_ESTABLISHED",
            human_calibration="NOT_RUN",
            new_http_requests=0,
            new_tokens=0,
            new_cost_usd=0,
            active_enabled=False,
        )
        assert (
            source_hashes() == frozen["app_experience"]
            and sha(Path(__file__)) == frozen["runner_sha256"]
        )
        save(output / "results.json", result)
        save(
            output / "validation.json",
            dict(
                source_unchanged=True,
                gold_unchanged=sha(HOLDOUT) == frozen["holdout_sha256"],
                business_databases_isolated=True,
                experience_database_isolated=True,
                network="BLOCKED_AND_MOCK_ONLY",
                paid_replay=False,
                source_refs_verified=True,
            ),
        )
        save(
            HERE / "experience_candidates/catalog_run_index.json",
            dict(
                run=str(output.relative_to(ROOT)),
                candidate_file="experience_candidates.json",
                record_count=len(candidates),
                scope="private synthetic offline analysis job; no production identity sharing",
            ),
        )
        print(json.dumps({k: v for k, v in result.items() if k not in {"E0_E1", "E2"}}))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "run"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    for name in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING", "LANGSMITH_TRACING"):
        os.environ[name] = "false"
    if args.command == "freeze":
        freeze()
    else:
        if not args.output:
            parser.error("new --output directory required")
        asyncio.run(evaluate(args.output.resolve()))
