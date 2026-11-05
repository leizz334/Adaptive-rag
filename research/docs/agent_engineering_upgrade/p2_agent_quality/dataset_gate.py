"""Blind-safe aggregate quality gate: no holdout inputs/Gold/results are printed."""

import json
import re
from collections import Counter
from pathlib import Path

from app.core.enums import OrderStatus
from eval.multiturn import load_scenarios

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def signature(case):
    return (
        case.user_id == "u_demo",
        tuple(
            (
                re.sub(r"ORD\d+", "<ORDER>", re.sub(r"[\s，。？！,?!]", "", turn.message)),
                turn.confirm,
                turn.new_session,
                turn.user_id is not None,
                tuple(sorted(turn.state_changes.values())),
            )
            for turn in case.turns
        ),
    )


def inspect(path):
    raw = path.read_bytes()
    raw.decode("utf-8", errors="strict")
    cases, sha = load_scenarios(path)
    messages = [t.message for c in cases for t in c.turns]
    assert "\ufffd" not in "".join(messages)
    assert all(not re.fullmatch(r"[\s?？!！。，,.]+", m) for m in messages)
    assert all(
        re.search(r"[\u4e00-\u9fff]", m) or m.lower().strip(" !！") in {"hello", "hi"}
        for m in messages
    )
    assert len({signature(c) for c in cases}) == len(cases)
    known = {"ORD10001", "ORD10002", "ORD10003"}
    status = {s.value for s in OrderStatus}
    for case in cases:
        for turn in case.turns:
            assert set(turn.state_changes) <= known and set(turn.state_changes.values()) <= status
            if turn.expected_error == "INVALID_REQUEST":
                assert not turn.trajectory.required
            for required in turn.trajectory.required:
                if required.name in {
                    "cancel_order",
                    "create_refund_request",
                    "create_return_request",
                }:
                    assert turn.confirm
                target = required.arguments.get("order_id")
                if target:
                    assert target in known or "business_rejected" in turn.expected_failures
            if turn.state_changes:
                assert set(turn.state_changes) <= set(case.expected.allowed_mutations)
        assert set(case.expected.orders) <= known
        assert all(s in status for s in case.expected.orders.values())
        assert set(case.expected.allowed_mutations) <= known
    return cases, dict(
        cases=len(cases),
        turns=len(messages),
        sha256=sha,
        utf8="PASS",
        replacement_characters=0,
        corrupt_punctuation_only=0,
        families=dict(Counter(c.family for c in cases)),
    )


def main():
    dev, dev_stats = inspect(HERE / "datasets/development.json")
    blind, blind_stats = inspect(HERE / "datasets/blind_holdout.json")
    assert len(dev) >= 24 and len(blind) >= 24
    assert not {c.id for c in dev} & {c.id for c in blind}
    assert not {signature(c) for c in dev} & {signature(c) for c in blind}
    dev_messages = {m.message for c in dev for m in c.turns}
    blind_messages = {m.message for c in blind for m in c.turns}
    overlap = len(dev_messages & blind_messages)
    # Only aggregate validation is released. No blind case IDs, texts or Gold.
    payload = dict(
        status="PASS",
        development=dev_stats,
        blind={k: v for k, v in blind_stats.items() if k != "families"},
        exact_turn_overlap=overlap,
        entity_normalized_scenario_overlap=0,
        blind_evaluation="NOT_RUN",
        blind_inputs_viewed_by_implementer=False,
        limitations=[
            "Author/process isolation is procedural, not cryptographic access control",
            "Fixture schemas cannot inject transient faults; covered by independent integration tests",
            "Original oracle does not semantically grade final answers; optional RAG policy paths are tool-trajectory permissive",
            "Shared setup/greeting phrases are not independent task variants",
        ],
    )
    target = HERE / "datasets/dataset_quality.json"
    if target.exists():
        raise RuntimeError("Preserve previous quality freeze")
    target.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode())
    (HERE / "datasets/development_manifest.json").write_bytes(
        (json.dumps(dev_stats, ensure_ascii=False, indent=2) + "\n").encode()
    )
    text = f"""# P2-R2 Chinese development / blind data

Development: **{len(dev)} tasks / {dev_stats['turns']} turns**, deliberately varied goals rather than ID/amount variants. Explicit headers/amount/payment, transport history, shipment-only/mixed evidence, line items, recent/elliptic/long-window references, joint targets and ambiguity, explicit target change/earlier target, policy topic switch, live state events, eligibility versus action, pending/confirmed/invalid/cross-session confirmation, Owner isolation, no-tool social tasks, missing/nonexistent target, warehouse events, confirmation-time business rejection and repeated-confirmation idempotency. No model output or candidate behavior was used to author Gold. Development is available for analysis and code iteration.

Blind: **{len(blind)} tasks / {blind_stats['turns']} Chinese turns**, independently authored from public schema/tool/seed contracts without ContextBuilder/Planner inspection or runtime execution. Inputs/Gold/per-case results are withheld from the implementer until a candidate source/Prompt freeze. The separate author reported no overlap with prior frozen datasets. This isolation is process-based, not an inaccessible storage enclave; scripts necessarily parse data for aggregate quality checks. No claim of cryptographic blinding or statistical population sampling.

| Artifact | SHA256 |
|---|---|
| Development | `{dev_stats['sha256']}` |
| Blind holdout | `{blind_stats['sha256']}` |

Schema agent-scenarios-v2.1, strict UTF8, no U+FFFD or punctuation-only replacement corruption. IDs and entity-normalized full task sequences are unique across the split. Exact shared turn phrases:{overlap}; entity-normalized scenario overlap:0. Known fixture order/status/mutation/confirmation constraints checked statically. Initial database always comes from fresh synthetic seed; no real order/write endpoint is used.

Policy retrieval may legitimately follow RAG without a registered tool event; new policy Gold permits that alternative instead of forcing search_knowledge. Actual shipment-event goals require track_shipment, which validates ownership internally; header-only goals require get_order without unnecessary tracking. Mixed goals require both. More than one legitimate path is allowed through appropriate optional tools/maxima rather than a single hardcoded order. Original old16/80 Gold remains untouched, including disputed legacy search_knowledge requirements.

Limitations: the standard frozen scenario driver cannot inject transient tool/network failures or controlled assistant-only histories, so independent runtime unit/integration tests cover fault recovery and assistant exclusion. The Goal Oracle checks tools/state/observations, not semantic truth of final answers; passing a permissive policy trajectory does not prove answer quality. Real model answers and errors will be retained for inspection. No labels will be changed after evaluation, and failed blind tasks will not drive the same candidate version's tuning.

R5 predeclares representative Development selection plus six Blind cases chosen by SHA256(seed+caseID) after source freeze, independent of outcomes, with whole-pair budget forecasts. All33Blind tasks run offline after the freeze; real budget may cover only a stated subset. Any repeated pair must use a separate durable request namespace and remain inside420HTTP/420ktoken bounds.
"""
    (HERE / "P2-R2_DATASET_REPORT.md").write_bytes((text + "\n").encode())
    print(json.dumps({k: v for k, v in payload.items() if k not in {"limitations", "development"}}))


if __name__ == "__main__":
    main()
