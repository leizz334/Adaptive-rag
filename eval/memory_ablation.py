"""Offline-only Memory ablations, unchanged P1 Gold/scorers. Never a real-model score."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import math
import os
import re
import subprocess
from pathlib import Path
from statistics import mean
from unittest.mock import patch

os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

# ruff: noqa: E402 -- disable ambient SaaS tracing before importing frameworks.
from app.agents.nodes.intent import rule_based_intent
from app.agents.nodes.planner import _knowledge_fallback, skill_to_plan
from app.memory.long_term import MemoryIdentity, PreferenceMemory, verified_memory_scope
from app.prompts.answer import ANSWER_SYSTEM
from app.prompts.complexity import COMPLEXITY_SYSTEM
from app.prompts.faithfulness import FAITHFULNESS_SYSTEM
from app.prompts.intent import INTENT_SYSTEM
from app.prompts.query_rewrite import REWRITE_SYSTEM
from app.prompts.self_rag import GRADE_SYSTEM
from app.providers.base import LLMResponse
from app.retrieval.adaptive import rule_based_complexity
from app.schemas.agent import IntentResult
from app.skills.loader import match_skill
from eval.environment import BusinessEnvironment
from eval.multiturn import Scenario, load_scenarios, run_scenarios

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "research/docs/agent_engineering_upgrade/p2_evidence"
REFERENCE_IDS = {"context_loss"} | {
    f"freshness_ORD1000{i}_pronoun_{c}" for i in (1, 2, 3) for c in ("stable", "changed")
}
HELDOUT_HASH = "f1200034a4048b20768ba2097bc408097f760dd7974ae8fe2ed093a15343fefc"


def query_field(text, prefix="用户问题："):
    return text.split(prefix, 1)[1].splitlines()[0].strip()


class ScriptedProvider:
    """Deterministic prompt-consuming fixture, no Gold, network, semantic judge or model."""

    def __init__(self):
        self.calls: list[dict] = []

    async def generate(self, messages, *, temperature=0.0, max_tokens=1024, response_format=None):
        system, user = messages[0]["content"], messages[-1]["content"]
        encoded = json.dumps(
            {"messages": messages, "response_format": response_format}, ensure_ascii=False
        ).encode()
        self.calls.append(
            {
                "input_utf8_bound": len(encoded) + 128,
                "output_reserve": max_tokens,
                "request_sha256": hashlib.sha256(encoded).hexdigest(),
                "temperature": temperature,
            }
        )
        if system == INTENT_SYSTEM:
            value = rule_based_intent(query_field(user)).model_dump(mode="json")
        elif system == COMPLEXITY_SYSTEM:
            query = query_field(user)
            intent = IntentResult(
                label=query_field(user, "意图："), confidence=1, prompt_version="offline"
            )
            value = rule_based_complexity(query, intent).model_dump(mode="json")
        elif system.startswith("你是电商客服规划器"):
            query = query_field(user)
            intent = query_field(user, "意图：")
            names = re.findall(r"^- ([a-z_]+):", system, re.M)

            class Catalog:
                def names(self):
                    return names

            skill = match_skill(query, intent)
            value = (
                skill_to_plan(skill, query, Catalog())
                if skill
                else _knowledge_fallback(query, Catalog())
            ).model_dump(mode="json")
        elif system == ANSWER_SYSTEM:
            text = user.split("工具结果：\n", 1)[1].split("\n\n输出 JSON", 1)[0]
            try:
                tools = json.loads(text)
            except ValueError:
                tools = []
            facts = [t["output"] for t in tools if t.get("success")]
            value = {
                "answer": json.dumps(facts, ensure_ascii=False) if facts else "离线固定证据答复",
                "citation_chunk_ids": [],
                "refused": False,
            }
        elif system == FAITHFULNESS_SYSTEM:
            value = {
                "status": "SUPPORTED",
                "supported": True,
                "rationale": "OFFLINE_SCRIPTED_NOT_A_SEMANTIC_JUDGE",
            }
        elif system == REWRITE_SYSTEM:
            value = {"queries": [query_field(user, "原始问题：")]}
        elif system == GRADE_SYSTEM:
            value = {"relevant": True, "sufficient": True, "missing_aspect": ""}
        else:
            raise AssertionError("Unsupported offline fixture prompt")
        return LLMResponse(
            json.dumps(value, ensure_ascii=False), model="offline-scripted-v1", finish_reason="stop"
        )

    async def ping(self):
        return True


async def run_arm(cases, digest, *, mode, scripted):
    providers = []

    def factory():
        provider = ScriptedProvider()
        providers.append(provider)
        return provider

    class Environment(BusinessEnvironment):
        async def __aenter__(self):
            result = await super().__aenter__()
            self.identity_scope = None
            if mode == "M3":
                store = PreferenceMemory()
                identity = MemoryIdentity("synthetic-test-tenant", "u_demo", verified=True)
                store.set_consent(identity, True, source="synthetic-consent-before-eval")
                store.upsert(identity, "language", "zh-CN", source="synthetic-prior-session:1")
                self.service._memory_store = store
                self.identity_scope = verified_memory_scope(identity)
                self.identity_scope.__enter__()
            return result

        async def __aexit__(self, *args):
            try:
                return await super().__aexit__(*args)
            finally:
                if self.identity_scope:
                    self.identity_scope.__exit__(*args)

    def environment(**kwargs):
        return Environment(memory_mode=mode, **kwargs)

    # Even a future accidental dependency path must not send a network request.
    with (
        patch("eval.multiturn.BusinessEnvironment", environment),
        patch(
            "socket.socket.connect",
            side_effect=AssertionError("Network forbidden in offline ablation"),
        ),
    ):
        results = await run_scenarios(
            cases, dataset_sha256=digest, tracing=False, llm_factory=factory if scripted else None
        )
    payloads = [r.model_dump() for r in results]
    if scripted:
        assert len(providers) == len(payloads)
        for result, provider in zip(payloads, providers, strict=True):
            result["offline_calls"] = provider.calls
    return {
        "mode": mode,
        "provider": "OFFLINE_SCRIPTED" if scripted else "OFFLINE_RULE",
        "real_model_evaluation": "NOT_RUN",
        "paid_api_calls": 0,
        "paid_tokens": 0,
        "offline_generated_responses": sum(len(p.calls) for p in providers),
        "estimated_input_utf8_bound": sum(
            c["input_utf8_bound"] for p in providers for c in p.calls
        ),
        "results": payloads,
    }


def summarize(results):
    n = len(results)
    turns = [t for r in results for t in r["evidence"]["turns"]]
    args = [
        t["scores"]["tool_argument_accuracy"]
        for t in turns
        if t["scores"]["tool_argument_accuracy"] is not None
    ]
    latency = sorted(r["metrics"]["latency_ms"] for r in results)
    refs = [r for r in results if r["case_id"] in REFERENCE_IDS]
    safety_tags = (
        "forbidden_",
        "protected_order",
        "unconfirmed_write",
        "cross_user_tool_output",
        "preexisting_row_changed",
        "order_created_or_deleted",
    )
    return {
        "cases": n,
        "passed": sum(r["status"] == "PASS" for r in results),
        "task_success": sum(r["status"] == "PASS" for r in results) / n if n else None,
        "reference_cases": len(refs),
        "reference_passed": sum(r["status"] == "PASS" for r in refs),
        "tool_selection": mean(t["scores"]["tool_selection_accuracy"] for t in turns)
        if turns
        else None,
        "tool_arguments": mean(args) if args else None,
        "environment_success": mean(r["metrics"]["environment_state_correct"] for r in results)
        if n
        else None,
        "safety_violations": [
            {"id": r["case_id"], "reason": reason}
            for r in results
            for reason in r["reasons"]
            if any(tag in reason for tag in safety_tags)
        ],
        "mean_latency_ms": mean(latency) if latency else None,
        "p95_latency_ms": latency[math.ceil(0.95 * n) - 1] if n else None,
        "estimated_input_utf8_bound": sum(
            c["input_utf8_bound"] for r in results for c in r.get("offline_calls", [])
        ),
        "scripted_calls": sum(len(r.get("offline_calls", [])) for r in results),
        "paid_tokens": 0,
        "real_model_tokens": "NOT_RUN",
    }


def long_window_case():
    from eval.contracts import EnvironmentExpectation, ToolExpectation, TrajectorySpec
    from eval.multiturn import Turn

    read = TrajectorySpec(
        required=[ToolExpectation(name="get_order", arguments={"order_id": "ORD10001"})],
        allowed=["get_order"],
        max_calls={"get_order": 1},
    )
    turns = [Turn(message="查询订单 ORD10001 状态", trajectory=read)]
    turns.extend(Turn(message="你好") for _ in range(6))
    turns.append(
        Turn(message="它现在是什么状态", trajectory=read, state_changes={"ORD10001": "delivered"})
    )
    return Scenario(
        id="p2_long_window",
        family="development_long_window_regression",
        user_goal="Read fresh order after old entity leaves window",
        turns=turns,
        expected=EnvironmentExpectation(
            orders={"ORD10001": "delivered"},
            allowed_mutations=["ORD10001"],
            observations=[
                ToolExpectation(
                    name="get_order", arguments={"order_id": "ORD10001", "status": "delivered"}
                )
            ],
        ),
    )


async def evaluate(output):
    if output.exists():
        raise SystemExit("Use a new output path; preserve previously evaluated results")
    original, digest = load_scenarios(ROOT / "eval/dataset/agent_v2_extended.json")
    heldout_path = EVIDENCE / "heldout_reference.json"
    assert hashlib.sha256(heldout_path.read_bytes()).hexdigest() == HELDOUT_HASH
    heldout, held_digest = load_scenarios(heldout_path)
    original_ids = {c.id for c in original}
    held_ids = {c.id for c in heldout}
    all_cases = original + heldout + [long_window_case()]
    combined = hashlib.sha256(
        (digest + held_digest + all_cases[-1].model_dump_json()).encode()
    ).hexdigest()
    value = {
        "status": "RUNNING",
        "pre_p2_head": "3c373ca502e2e08b4a343d751500c7ce77b28415",
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "original_dataset_sha256": digest,
        "heldout_sha256": held_digest,
        "combined_sha256": combined,
        "real_model_evaluation": "NOT_RUN",
        "paid_api_calls": 0,
        "paid_tokens": 0,
        "json_reliability_control": "Identical P2-A repair in every arm; M0 is reliability-only/no-history. Real JSON-only improvement NOT_RUN.",
        "m3_scope": "Synthetic verified request principals only; production cross-session memory disabled",
        "arms": [],
    }

    def save():
        output.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    save()
    for scripted in (False, True):
        for mode in ("M0", "M1", "M2", "M3"):
            # Rule arms cover all unchanged P1 cases; scripted arms additionally exercise all node inputs.
            arm = await run_arm(all_cases, combined, mode=mode, scripted=scripted)
            groups = {
                "original80": [r for r in arm["results"] if r["case_id"] in original_ids],
                "original7": [r for r in arm["results"] if r["case_id"] in REFERENCE_IDS],
                "heldout12": [r for r in arm["results"] if r["case_id"] in held_ids],
                "long_window": [r for r in arm["results"] if r["case_id"] == "p2_long_window"],
            }
            arm["groups"] = {key: summarize(rows) for key, rows in groups.items()}
            value["arms"].append(arm)
            save()
            print(
                json.dumps(
                    {
                        "provider": arm["provider"],
                        "mode": mode,
                        "original80": arm["groups"]["original80"]["passed"],
                        "reference7": arm["groups"]["original7"]["passed"],
                        "heldout12": arm["groups"]["heldout12"]["passed"],
                        "long_window": arm["groups"]["long_window"]["passed"],
                    }
                ),
                flush=True,
            )
    value["status"] = "COMPLETED_OFFLINE_ONLY"
    save()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    asyncio.run(evaluate(args.output))


if __name__ == "__main__":
    main()
