"""Evidence must observe the actual service without changing the frozen oracles."""

import json
import socket
from pathlib import Path

import pytest

from eval.memory_ablation import run_arm
from eval.multiturn import load_scenarios
from research.docs.agent_engineering_upgrade.p2_agent_quality import instrumented as r

OLD16 = Path(__file__).resolve().parents[1] / "p2_quality/new_unseen.json"


def outcome(row):
    return {
        "case_id": row["case_id"],
        "status": row["status"],
        "reasons": row["reasons"],
        "environment": row["metrics"]["environment_state_correct"],
        "turns": [
            {k: turn[k] for k in ("turn", "error", "scores", "pending", "refused")}
            for turn in row["evidence"]["turns"]
        ],
    }


@pytest.mark.parametrize("case_id", ["nu01", "nu10"])
async def test_real_node_capture_and_unchanged_original_oracles(case_id):
    cases, digest = load_scenarios(OLD16)
    case = next(case for case in cases if case.id == case_id)
    normal = await run_arm([case], digest, mode="M2", scripted=True)
    captured = await r.evaluate_cases([case], dataset_sha256=digest)
    assert outcome(captured["results"][0]) == outcome(normal["results"][0])
    assert captured["model_evaluation"] == "OFFLINE"
    trace = captured["traces"][0]
    assert trace["case_id"] == case_id
    assert trace["evidence_origin"] == "SOURCEFROZEN_REEXECUTION"
    assert len(trace["turns"]) == len(case.turns)
    first = trace["turns"][0]
    assert first["initial_state"]["user_query"] == case.turns[0].message
    assert "selected_context" in first["initial_state"]
    nodes = first["nodes"]
    assert nodes[0]["node"] == "apply_guardrail"
    assert [n["sequence"] for n in nodes] == list(range(len(nodes)))
    assert any(n["node"] == "classify_intent" for n in nodes)
    assert any(n["node"] == "compact_memory" for n in nodes)
    assert first["response"]["answer"] == first["final_state"]["final_answer"]
    assert first["database_after"]["tables"]["messages"]
    assert "ORD10003" in first["database_after"]["business"]["orders"]
    assert trace["database_final"]["tables"]["sessions"]
    if case_id == "nu10":
        error = trace["turns"][1]
        assert error["error"]["code"] == "INVALID_REQUEST"
        assert error["nodes"] == []
        assert "initial_state" not in error
        assert (
            error["database_after"]["tables"]["messages"]
            == first["database_after"]["tables"]["messages"]
        )
    json.dumps(captured, ensure_ascii=False)


def test_serializer_excludes_hidden_and_unsupported_objects():
    assert r.safe_value({"rationale": "private", "answer": "synthetic"}) == {"answer": "synthetic"}
    with pytest.raises(TypeError):
        r.safe_value(object())


def test_network_guard_blocks_connections_and_restores():
    original = socket.socket.connect
    with r.offline_network():
        with pytest.raises(AssertionError, match="Network forbidden"):
            socket.create_connection(("example.com", 443))
    assert socket.socket.connect is original


async def test_output_is_new_and_contains_hashes_and_raw_scorer(tmp_path):
    cases, digest = load_scenarios(OLD16)
    target = tmp_path / "new-run"
    await r.evaluate_to_directory(cases[:1], dataset_sha256=digest, output=target, dataset=OLD16)
    config = json.loads((target / "experiment_config.json").read_text(encoding="utf-8"))
    assert config["dataset_sha256"] == digest
    assert config["source_hashes"]["app/agents/graph.py"]
    assert config["prompt_hashes"]["app/prompts/planner.py"]
    assert config["scorer_hashes"]["eval/multiturn.py"]
    assert config["network"] == "FORBIDDEN"
    raw = json.loads((target / "results.json").read_text(encoding="utf-8"))
    assert raw["model_evaluation"] == "OFFLINE"
    assert (target / "traces/000_nu01.json").exists()
    before = (target / "results.json").read_bytes()
    with pytest.raises(FileExistsError):
        await r.evaluate_to_directory(
            cases[:1], dataset_sha256=digest, output=target, dataset=OLD16
        )
    assert (target / "results.json").read_bytes() == before
