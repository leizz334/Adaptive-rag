"""One-shot authenticated live acceptance, guarded by the existing durable ledger."""

import hashlib
import json
import logging
import os
import subprocess
import time
from decimal import Decimal
from pathlib import Path

import httpx

logging.disable(logging.CRITICAL)
os.umask(0o077)
ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/deepseek_live_acceptance"
OUT = HERE / "evidence"
PRIVATE = Path("/home/panda/.adaptive-rag-live-20261114")
API = "adaptive-rag-real-agent-dev-api-1"
BASE = "http://127.0.0.1:8001/api/v1"


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Container evidence query failed; no diagnostic secrets emitted")
    return result.stdout


def ledger():
    code = """
import json
from urllib.parse import urlsplit
from app.demo.real_dev import load_runtime_config
from app.providers.paid_budget import AttemptLedger
c=load_runtime_config()
u=urlsplit(c.settings.deepseek_base_url)
assert c.settings.deepseek_model==c.limits.model=='deepseek-flash'
assert u.scheme=='https' and u.hostname=='api.deepseek.com' and u.port in {None,443} and u.path.rstrip('/') in {'','/v1'} and not(u.username or u.password or u.query or u.fragment)
assert (c.limits.max_requests,c.limits.max_tokens,str(c.limits.max_usd),str(c.limits.input_usd_per_million),str(c.limits.output_usd_per_million))==(6,10000,'0.05','0.30','1.20')
assert c.settings.llm_max_retries==1 and c.settings.deepseek_thinking_mode=='disabled'
b=AttemptLedger(c.budget_path,c.limits)
print(json.dumps(b.snapshot()))
"""
    result = json.loads(docker("exec", API, "python", "-c", code))
    assert (
        result["requests"] <= 6
        and result["tokens"] <= 10000
        and Decimal(result["usd"]) <= Decimal("0.05")
    )
    return result


def save(name, value):
    with (OUT / name).open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


assert json.loads((OUT / "D2-preflight.json").read_text())["exit"] == 0
assert json.loads((OUT / "D2-startup.json").read_text())["ledger"]["requests"] == 0
assert not (OUT / "D3-started.json").exists(), "Never replay a live run automatically"
assert (
    ledger()["requests"] == 0
), "Existing usage requires explicit reconciliation; never reset ledger"
env_hash = json.loads((OUT / "D1-baseline.json").read_text())["env_sha256"]
assert hashlib.sha256((ROOT / ".env").read_bytes()).hexdigest() == env_hash
tokens = json.loads(
    docker(
        "exec",
        API,
        "python",
        "-c",
        'import json;from app.demo.docker import read_credentials;print(json.dumps(read_credentials()["tokens"]))',
    )
)
client = httpx.Client(timeout=150, trust_env=False)


def request(method, path, data=None, subject="a"):
    headers = {"Authorization": "Bearer " + tokens[subject]} if subject else {}
    return client.request(method, BASE + path, json=data, headers=headers)


identity = request("GET", "/auth/me")
assert identity.status_code == 200 and identity.json()["subject"] == "web_demo_a"
assert request("GET", "/auth/me", subject=None).status_code == 401
caps = request("GET", "/capabilities")
assert caps.status_code == 200 and caps.json()["llm"] == "deepseek"
ready = request("GET", "/ready").json()
assert all(
    d["ready"] for d in ready["dependencies"] if d["name"] in {"database", "redis", "vector_store"}
)
save(
    "D3-started.json",
    {
        "model": "deepseek-flash",
        "transport": "real authenticated HTTP to existing RealDev; no MockTransport",
        "limits": {"requests": 6, "reserved_tokens": 10000, "estimated_usd": "0.05"},
        "ledger_before": ledger(),
        "capabilities": caps.json(),
    },
)


def chat_case(name, message, session_id=None, stream=False):
    before = ledger()
    if before["pending"] or before["uncertain"]:
        return {"name": name, "status": "NOT_RUN_UNCERTAIN_LEDGER", "ledger": before}
    started = time.monotonic()
    data = {"message": message}
    if session_id:
        data["session_id"] = session_id
    response = request("POST", "/chat/stream" if stream else "/chat", data)
    events = (
        [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith("data:")]
        if stream
        else []
    )
    answer = (
        next((e["data"] for e in events if e.get("event") == "answer"), None)
        if stream
        else response.json()
        if response.status_code == 200
        else None
    )
    result = {
        "name": name,
        "http_status": response.status_code,
        "latency_ms": round((time.monotonic() - started) * 1000),
        "ledger_before": before,
        "ledger_after": ledger(),
        "sse_events": events if stream else None,
        "status": "PENDING_VALIDATION",
    }
    result["actual_model_http_requests"] = result["ledger_after"]["requests"] - before["requests"]
    if answer:
        result["answer"] = answer
        trace_response = request(
            "GET", f'/sessions/{answer["session_id"]}/traces/{answer["root_run_id"]}'
        )
        if trace_response.status_code == 200:
            trace = trace_response.json()
            result["trace"] = trace
            spans = [s for s in trace["spans"] if s["kind"] == "llm"]
            result["api_success_requests"] = sum(
                bool(s["status"] == "ok" and s["metadata"].get("usage_known")) for s in spans
            )
            result["usage"] = {
                key: sum(s["metadata"].get(key, 0) for s in spans)
                for key in ["prompt_tokens", "completion_tokens", "total_tokens"]
            }
            result["actual_usage_complete"] = result["api_success_requests"] == result[
                "actual_model_http_requests"
            ] and all(s["metadata"].get("total_tokens", 0) > 0 for s in spans)
            result["estimated_usage_cost_upper_usd"] = str(
                (
                    Decimal(result["usage"]["prompt_tokens"]) * Decimal("0.30")
                    + Decimal(result["usage"]["completion_tokens"]) * Decimal("1.20")
                )
                / Decimal(1000000)
            )
    if response.status_code != 200:
        result["error"] = response.json()
    if any(e.get("event") == "error" for e in events):
        result["error"] = next(e for e in events if e.get("event") == "error")
    if result["ledger_after"]["pending"] or result["ledger_after"]["uncertain"]:
        result["status"] = "STOP_UNCERTAIN_BILLING"
    elif result.get("error"):
        result["status"] = (
            "BUDGET_BLOCKED"
            if result["actual_model_http_requests"] == 0
            and result["error"].get("message") == "paid provider budget admission blocked"
            else "FAILED_STOP_FOR_DIAGNOSIS"
        )
    elif not result.get("actual_usage_complete"):
        result["status"] = "FAILED_STOP_USAGE_OR_PROVIDER_DIAGNOSIS"
    elif result["usage"]["total_tokens"] > result["ledger_after"]["tokens"] - before["tokens"]:
        result["status"] = "STOP_USAGE_EXCEEDS_RESERVATION"
    else:
        result["status"] = "LIVE_RESPONSE_RECEIVED"
    return result


results = []
greeting = chat_case("greeting", "你好")
if (
    greeting["status"] == "LIVE_RESPONSE_RECEIVED"
    and greeting.get("api_success_requests", 0) > 0
    and greeting.get("answer", {}).get("answer")
    and not greeting["answer"].get("refused")
):
    greeting["status"] = "PASS_REAL_AGENT"
results.append(greeting)
save("D3-greeting.json", greeting)
if greeting["status"] == "PASS_REAL_AGENT":
    session = greeting["answer"]["session_id"]
    tool = chat_case(
        "tool_order", "请查询 ORD95101 的订单状态和金额", session_id=session, stream=True
    )
    if tool["status"] == "LIVE_RESPONSE_RECEIVED":
        matching = [
            t
            for t in tool.get("trace", {}).get("tools", [])
            if t["name"] == "get_order" and t["success"] and t["result"].get("total_cents") == 6800
        ]
        tool["status"] = "PASS_REAL_AGENT" if matching else "FAIL_TOOL_EVIDENCE"
    results.append(tool)
    save("D3-tool-order.json", tool)
    minimum_intent = json.loads((OUT / "D2-greeting-forecast.json").read_text())["requests"][0][
        "reserved_tokens"
    ]

    def can_continue():
        snap = ledger()
        return (
            not (snap["pending"] or snap["uncertain"])
            and snap["requests"] < 6
            and 10000 - snap["tokens"] >= minimum_intent
            and results[-1]["status"] in {"PASS_REAL_AGENT", "LIVE_RESPONSE_RECEIVED"}
        )

    if tool["status"] == "PASS_REAL_AGENT" and can_continue():
        memory = chat_case("memory", "这单的商品明细和是否定制也帮我核实", session_id=session)
        if memory["status"] == "LIVE_RESPONSE_RECEIVED":
            proven = any(
                t["name"] == "get_order_items" and t["success"]
                for t in memory.get("trace", {}).get("tools", [])
            )
            memory["status"] = (
                "PASS_REAL_AGENT"
                if proven and memory["trace"]["memory"]["message_count"] > 0
                else "FAIL_MEMORY_EVIDENCE"
            )
        results.append(memory)
        save("D3-memory.json", memory)
    else:
        results.append(
            {
                "name": "memory",
                "status": "NOT_RUN_BUDGET_OR_TOOL_PRECONDITION",
                "actual_model_http_requests": 0,
            }
        )
    # This is an authenticated retrieval check, explicitly not a live LLM policy answer.
    doc = "deepseek-live-synthetic-policy-20261114"
    policy = "定制商品不适用七天无理由退货；如存在质量问题，超过七天仍可申请售后退换，须提供合成订单和质量证明，最终按审核处理。本段仅供隔离演示，并非真实商家政策。"
    uploaded = request(
        "POST", "/knowledge/documents/" + doc, {"title": "合成定制商品售后政策", "content": policy}
    )
    assert uploaded.status_code == 200
    retrieved = request(
        "POST",
        "/knowledge/search",
        {"query": "定制商品过了七天，但有质量问题还能退吗？", "mode": "hybrid"},
    )
    foreign = request(
        "POST", "/knowledge/search", {"query": "定制商品质量问题", "mode": "hybrid"}, subject="b"
    )
    assert retrieved.status_code == 200 and any(
        c["document_id"] == doc for c in retrieved.json()["chunks"]
    )
    assert not any(c["document_id"] == doc for c in foreign.json()["chunks"])
    save(
        "D3-retrieval-only.json",
        {
            "status": "PASS_AUTHENTICATED_RETRIEVAL_ONLY_NOT_LIVE_LLM_RAG",
            "document_id": doc,
            "own_hits": len(retrieved.json()["chunks"]),
            "foreign_hits": len(foreign.json()["chunks"]),
            "model_http_requests": 0,
            "policy_retained_in_isolated_project": True,
        },
    )
    if can_continue():
        rag = chat_case("rag_policy_answer", "定制商品过了七天，但有质量问题还能退吗？")
        if rag["status"] == "LIVE_RESPONSE_RECEIVED":
            rag["status"] = (
                "PASS_REAL_AGENT"
                if any(c["document_id"] == doc for c in rag.get("answer", {}).get("citations", []))
                else "FAIL_RAG_CITATION"
            )
        results.append(rag)
        save("D3-rag.json", rag)
    else:
        results.append(
            {
                "name": "rag_policy_answer",
                "status": "NOT_RUN_BUDGET_OR_PRIOR_FAILURE",
                "actual_model_http_requests": 0,
            }
        )
    if can_continue():
        negative = chat_case("negative_order", "请查询订单 ORD999999999 的状态")
        if negative["status"] == "LIVE_RESPONSE_RECEIVED":
            negative["status"] = (
                "PASS_REAL_AGENT"
                if any(
                    not t["success"] and t["name"] == "get_order"
                    for t in negative.get("trace", {}).get("tools", [])
                )
                else "FAIL_NEGATIVE_EVIDENCE"
            )
        results.append(negative)
        save("D3-negative.json", negative)
    else:
        results.append(
            {
                "name": "negative_order",
                "status": "NOT_RUN_BUDGET_OR_PRIOR_FAILURE",
                "actual_model_http_requests": 0,
            }
        )
    history = request("GET", f"/sessions/{session}/messages")
    other = request("GET", f"/sessions/{session}/messages", subject="b")
    assert history.status_code == 200 and other.status_code == 404
    messages = history.json()["messages"]
    assert any(m["role"] == "user" and m["content"] == "你好" for m in messages)
    assert any(
        m["role"] == "assistant" and m["content"] == greeting["answer"]["answer"] for m in messages
    )
    save(
        "D3-history-only.json",
        {
            "status": "PASS_PERSISTED_REAL_GREETING_HISTORY_NOT_ORDER_MULTITURN_ACCEPTANCE",
            "own_status": history.status_code,
            "message_count": len(history.json()["messages"]),
            "foreign_status": other.status_code,
        },
    )
else:
    results.extend(
        [
            {"name": name, "status": "NOT_RUN_AFTER_FIRST_FAILURE", "actual_model_http_requests": 0}
            for name in ["tool_order", "memory", "rag_policy_answer", "negative_order"]
        ]
    )
final = ledger()
known = [r for r in results if r.get("actual_usage_complete")]
summary = {
    "results": [
        {
            "name": r["name"],
            "status": r["status"],
            "actual_model_http_requests": r.get("actual_model_http_requests", 0),
            "latency_ms": r.get("latency_ms"),
            "usage": r.get("usage"),
        }
        for r in results
    ],
    "ledger": final,
    "api_success_requests": sum(r.get("api_success_requests", 0) for r in results),
    "actual_usage_total": {
        k: sum(r.get("usage", {}).get(k, 0) for r in results)
        for k in ["prompt_tokens", "completion_tokens", "total_tokens"]
    },
    "estimated_usage_cost_upper_usd": str(
        sum((Decimal(r.get("estimated_usage_cost_upper_usd", "0")) for r in results), Decimal(0))
    ),
    "usage_known_for_all_dispatched_requests": sum(r.get("api_success_requests", 0) for r in known)
    == final["requests"],
    "billing_statement_verified": False,
    "limits_preserved": final["requests"] <= 6
    and final["tokens"] <= 10000
    and Decimal(final["usd"]) <= Decimal("0.05"),
    "automatic_paid_retries": False,
}
save("D3-summary.json", summary)
print(json.dumps(summary, ensure_ascii=True))
client.close()
