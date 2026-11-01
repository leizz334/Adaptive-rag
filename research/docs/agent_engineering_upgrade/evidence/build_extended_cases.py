"""Freeze a predeclared 80-case matrix, never inspect Agent outputs for labels."""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "eval/dataset"


def query(order):
    return {
        "message": f"查询订单 {order} 状态",
        "trajectory": {
            "required": [{"name": "get_order", "arguments": {"order_id": order}}],
            "allowed": ["get_order", "track_shipment", "search_knowledge"],
            "max_calls": {"search_knowledge": 2},
        },
    }


def proposal():
    return {"message": "取消订单 ORD10003", "expected_pending": True}


def confirmation(order="ORD10003", rejected=False):
    return {
        "message": "确认取消",
        "confirm": True,
        "expected_failures": ["business_rejected"] if rejected else [],
        "trajectory": {"required": [{"name": "cancel_order", "arguments": {"order_id": order}}]},
    }


def cancelled():
    return {
        "orders": {"ORD10003": "cancelled"},
        "allowed_mutations": ["ORD10003"],
        "audit_actions": ["cancel_order"],
    }


def build():
    seed = json.loads((DATA / "agent_v2.json").read_text(encoding="utf-8"))
    cases = deepcopy(seed["scenarios"])
    states = {"ORD10001": "shipped", "ORD10002": "delivered", "ORD10003": "paid"}
    for order in states:
        for actor in ["u_demo", "other", "anonymous"]:
            turn = query(order)
            if actor != "u_demo":
                turn["expected_failures"] = ["business_rejected"]
            expected = (
                {
                    "observations": [
                        {
                            "name": "get_order",
                            "arguments": {"order_id": order, "status": states[order]},
                        }
                    ]
                }
                if actor == "u_demo"
                else {}
            )
            cases.append(
                dict(
                    id=f"owner_{order}_{actor}",
                    family="ownership_matrix",
                    user_goal="Observe owned order only; deny foreign data without mutation",
                    user_id=actor,
                    turns=[turn],
                    expected=expected,
                )
            )
    for first in states:
        for second in states:
            cases.append(
                dict(
                    id=f"query_pair_{first}_{second}",
                    family="explicit_query_matrix",
                    user_goal="Read explicit second target, including repeated fresh query",
                    turns=[query(first), query(second)],
                    expected={
                        "observations": [
                            {
                                "name": "get_order",
                                "arguments": {"order_id": second, "status": states[second]},
                            }
                        ]
                    },
                )
            )
    for order, state in states.items():
        for actor in ["u_demo", "other"]:
            for replay in [False, True]:
                can_cancel = actor == "u_demo" and state == "paid"
                turns = [
                    {"message": f"取消订单 {order}", "expected_pending": True},
                    confirmation(order, not can_cancel),
                ]
                if replay:
                    turns.append(confirmation(order, not can_cancel))
                expected = cancelled() if can_cancel else {"orders": {order: state}}
                cases.append(
                    dict(
                        id=f"cancel_matrix_{order}_{actor}_{replay}",
                        family="cancellation_state_matrix",
                        user_goal="Only owner of paid unshipped order may cancel; repeated confirm has no repeated commit",
                        user_id=actor,
                        turns=turns,
                        expected=expected,
                    )
                )
    for actor in ["other", "anonymous"]:
        for new_session in [False, True]:
            for recover in [False, True]:
                turns = [
                    proposal(),
                    {
                        "message": "确认",
                        "confirm": True,
                        "user_id": actor,
                        "new_session": new_session,
                        "expected_error": "INVALID_REQUEST",
                    },
                ]
                if recover:
                    turns.append(confirmation())
                cases.append(
                    dict(
                        id=f"stolen_confirmation_{actor}_{new_session}_{recover}",
                        family="confirmation_identity_matrix",
                        user_goal="Reject wrong actor/session; optionally recover with original owner",
                        turns=turns,
                        expected=cancelled() if recover else {},
                    )
                )
    for new_session in [False, True]:
        for recover in [False, True]:
            turns = [
                proposal(),
                {
                    "message": "确认",
                    "invalid_confirmation": True,
                    "new_session": new_session,
                    "expected_error": "INVALID_REQUEST",
                },
            ]
            if recover:
                turns.append(confirmation())
            cases.append(
                dict(
                    id=f"invalid_action_{new_session}_{recover}",
                    family="invalid_action_matrix",
                    user_goal="Unknown action must not execute; valid original action may recover",
                    turns=turns,
                    expected=cancelled() if recover else {},
                )
            )
    for actor in ["u_demo", "other"]:
        for target in ["ORD10001", "ORD10002", "ORD99999"]:
            for intrusion in [False, True]:
                turns = [proposal()]
                if intrusion:
                    turns.append(
                        {
                            "message": "确认",
                            "confirm": True,
                            "user_id": "other" if actor == "u_demo" else "u_demo",
                            "expected_error": "INVALID_REQUEST",
                        }
                    )
                last = confirmation(rejected=actor != "u_demo")
                last["message"] = f"确认取消订单 {target}"
                turns.append(last)
                cases.append(
                    dict(
                        id=f"binding_{actor}_{target}_{intrusion}",
                        family="parameter_binding_matrix",
                        user_goal="Confirmation words cannot replace approved order, and approvals cannot be stolen",
                        user_id=actor,
                        turns=turns,
                        expected=cancelled() if actor == "u_demo" else {},
                    )
                )
    changed_states = {"ORD10001": "delivered", "ORD10002": "refunding", "ORD10003": "shipped"}
    for order, original in states.items():
        for wording in ["explicit", "pronoun"]:
            for changed in [False, True]:
                current = changed_states[order] if changed else original
                second = query(order)
                if wording == "pronoun":
                    second["message"] = "它现在是什么状态"
                second["state_changes"] = {order: current} if changed else {}
                cases.append(
                    dict(
                        id=f"freshness_{order}_{wording}_{'changed' if changed else 'stable'}",
                        family="freshness_context_matrix",
                        user_goal="Observe authoritative current state after optional external environment event; history cannot substitute a fresh read",
                        turns=[query(order), second],
                        expected={
                            "orders": {order: current},
                            "allowed_mutations": [order] if changed else [],
                            "observations": [
                                {
                                    "name": "get_order",
                                    "arguments": {"order_id": order, "status": current},
                                }
                            ],
                        },
                        known_limitation="Pronoun resolution may fail until P2; keep failure visible"
                        if wording == "pronoun"
                        else None,
                    )
                )
    assert len(cases) == 80 and len({c["id"] for c in cases}) == 80
    return {
        "schema_version": "agent-scenarios-v2.1",
        "labeling": "Original frozen 14 unchanged + 66 predeclared parameter-matrix variants. Gold derived from fixture ownership/state/approval invariants, not model answers. Variants in same family are NOT independent statistical samples.",
        "scenarios": cases,
    }


if __name__ == "__main__":
    target = DATA / "agent_v2_extended.json"
    assert not target.exists(), "Frozen dataset exists: do not overwrite or relabel from results"
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target.write_bytes(raw)
    freeze = {
        "frozen_before_first_run_utc": datetime.now(UTC).isoformat(),
        "cases": 80,
        "seed_cases": 14,
        "matrix_variants": 66,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "gold_source": "predeclared fixture invariants; no Agent result inspection",
    }
    (Path(__file__).parent / "P1-extended-dataset-freeze.json").write_bytes(
        (json.dumps(freeze, indent=2) + "\n").encode("utf-8")
    )
    print(json.dumps(freeze))
