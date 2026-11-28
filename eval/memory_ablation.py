"""Network-blocked fixtures for memory and tool regression tests."""

from __future__ import annotations

import hashlib
import json
import os
import re
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
from eval.multiturn import run_scenarios


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
