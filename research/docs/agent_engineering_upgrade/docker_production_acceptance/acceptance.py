"""Actual production HTTP/SSE acceptance; only synthetic fixture writes."""

import json
import logging
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

logging.disable(logging.CRITICAL)
os.umask(0o077)
HERE = Path.cwd() / "research/docs/agent_engineering_upgrade/docker_production_acceptance"
OUT = HERE / "evidence"
RUN = str(int(time.time()))
API = "adaptive-rag-showcase-api-1"
tokens = json.loads(
    subprocess.check_output(
        [
            "docker",
            "exec",
            API,
            "python",
            "-c",
            'import json;from app.demo.docker import read_credentials;print(json.dumps(read_credentials()["tokens"]))',
        ],
        text=True,
    )
)
http = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def req(method, path, data=None, subject="a", expected=200, stream=False):
    headers = {"Content-Type": "application/json"}
    if subject:
        headers["Authorization"] = "Bearer " + tokens[subject]
    request = urllib.request.Request(
        "http://127.0.0.1:8000/api/v1" + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
        method=method,
    )
    try:
        response = http.open(request, timeout=60)
    except urllib.error.HTTPError as exc:
        response = exc
    assert (
        response.code == expected
    ), f"HTTP {method} {path} status {response.code} expected {expected}"
    text = response.read().decode()
    if stream:
        return [json.loads(line[5:]) for line in text.splitlines() if line.startswith("data:")]
    return json.loads(text)


def sql(query):
    return json.loads(
        subprocess.check_output(
            [
                "docker",
                "exec",
                "adaptive-rag-showcase-postgres-1",
                "psql",
                "-U",
                "adaptive",
                "-d",
                "adaptive_showcase",
                "-Atc",
                query,
            ],
            text=True,
        )
    )


def save(name, value):
    with (OUT / name).open("x") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)


def trace(answer):
    result = req("GET", f'/sessions/{answer["session_id"]}/traces/{answer["root_run_id"]}')
    save("trace-" + answer["root_run_id"] + ".json", result)
    return result


checks = {}
req("GET", "/auth/me", subject=None, expected=401)
identity = req("GET", "/auth/me")
assert identity["subject"] == "web_demo_a"
ready = req("GET", "/ready")
assert all(
    d["ready"] for d in ready["dependencies"] if d["name"] in ["database", "redis", "vector_store"]
)
cap = req("GET", "/capabilities")
save("capabilities.json", cap)
checks["health_auth"] = "PASS"

first = req("POST", "/chat", {"message": "请查询 ORD95101 的订单状态和金额"})
t1 = trace(first)
actual = sql(
    "SELECT row_to_json(t) FROM (SELECT order_id,status,total_cents FROM orders WHERE order_id='ORD95101') t"
)
tool = next(t for t in t1["tools"] if t["name"] == "get_order")
assert tool["result"]["total_cents"] == actual["total_cents"] == 6800
assert tool["result"]["status"] == actual["status"] and "68" in first["answer"]
events = req(
    "POST",
    "/chat/stream",
    {"message": "这单的商品明细和是否定制也帮我核实", "session_id": first["session_id"]},
    stream=True,
)
assert not any(e["event"] == "error" for e in events)
second = next(e["data"] for e in events if e["event"] == "answer")
t2 = trace(second)
assert second["session_id"] == first["session_id"] and "演示帆布包" in second["answer"]
assert t2["memory"]["mode"] == "M2" and t2["memory"]["message_count"] > 0
assert any(t["name"] == "get_order_items" and t["result"]["item_count"] == 1 for t in t2["tools"])
req("GET", f'/sessions/{first["session_id"]}/messages', subject="b", expected=404)
save(
    "order-memory-sse.json",
    {
        "database": actual,
        "http": first,
        "sse_answer": second,
        "events": [e["event"] for e in events],
        "memory": t2["memory"],
    },
)
checks["order_memory_http_sse_trace"] = "PASS"

doc = "production-policy-" + RUN
title = "琥珀" + RUN + "会员退货政策"
question = title + "是什么？"
missing = req("POST", "/chat", {"message": question})
assert not missing["citations"]
save("missing-policy.json", missing)
req(
    "POST",
    "/knowledge/documents/" + doc,
    {
        "title": title,
        "content": f"# {title}\n{title}：合成演示商品签收后三十天内允许退货，需提供合成凭证。仅用于本轮隔离验收。",
    },
)
try:
    search = req("POST", "/knowledge/search", {"query": title, "mode": "hybrid"})
    assert any(c["document_id"] == doc for c in search["chunks"])
    foreign = req("POST", "/knowledge/search", {"query": title, "mode": "hybrid"}, subject="b")
    assert not any(c["document_id"] == doc for c in foreign["chunks"])
    req("DELETE", "/knowledge/documents/" + doc, subject="b", expected=404)
    grounded = req("POST", "/chat", {"message": question})
    gt = trace(grounded)
    assert (
        any(c["document_id"] == doc for c in grounded["citations"])
        and "三十天" in grounded["answer"]
    )
    assert any(c["document_id"] == doc for c in gt["retrieval"])
    save(
        "rag-owner.json",
        {
            "document": doc,
            "answer": grounded,
            "foreign_delete": 404,
            "foreign_hit_count": len(foreign["chunks"]),
        },
    )
finally:
    req("DELETE", "/knowledge/documents/" + doc)
checks["private_rag_citations_owner"] = "PASS"

foreign_order = req("POST", "/chat", {"message": "查询 ORD95101 的订单状态"}, subject="b")
assert "6800" not in foreign_order["answer"] and "68.00" not in foreign_order["answer"]
req(
    "POST",
    "/chat",
    {"message": "查询 ORD95101", "user_id": "web_demo_a"},
    subject="b",
    expected=403,
)
unknown = req("POST", "/chat", {"message": "查询 ORD999999999 的订单状态"})
assert any(
    word in unknown["answer"] for word in ["未找到", "不存在", "无法", "没有", "失败", "未查询"]
)
save(
    "negative-owner.json",
    {"foreign_order": foreign_order, "nonexistent_order": unknown, "forged_owner": 403},
)
checks["negative_and_identity"] = "PASS"

order = "ORD95107"
before = sql(
    "SELECT row_to_json(t) FROM (SELECT order_id,user_id,status,total_cents FROM orders WHERE order_id='ORD95107') t"
)
assert before == {
    "order_id": order,
    "user_id": "web_demo_a",
    "status": "paid",
    "total_cents": 6800,
}, "Only pristine documented synthetic order may be cancelled"
proposal = req("POST", "/chat", {"message": "请取消订单 " + order})
pt = trace(proposal)
assert proposal["pending_action"]["tool_name"] == "cancel_order"
assert sql("SELECT to_json(status) FROM orders WHERE order_id='ORD95107'") == "paid"
action = proposal["pending_action"]["action_id"]
path = f'/sessions/{proposal["session_id"]}/actions/{action}'
req("POST", path + "/cancel", subject="b", expected=404)
payload = {
    "message": "确认执行",
    "session_id": proposal["session_id"],
    "confirm_action_id": action,
    "idempotency_key": action,
}
confirmed = req("POST", "/chat", payload)
after = sql(
    "SELECT json_build_object('status',(SELECT status FROM orders WHERE order_id='ORD95107'),'audits',(SELECT count(*) FROM audit_logs),'idempotency',(SELECT count(*) FROM idempotency_keys))"
)
replay = req("POST", "/chat", payload)
replayed = sql(
    "SELECT json_build_object('status',(SELECT status FROM orders WHERE order_id='ORD95107'),'audits',(SELECT count(*) FROM audit_logs),'idempotency',(SELECT count(*) FROM idempotency_keys))"
)
assert after == replayed and after["status"] == "cancelled"
assert "已取消" in confirmed["answer"] and "已取消" in replay["answer"]
assert req("GET", path)["status"] == "completed"
req("POST", path + "/cancel", expected=409)
save(
    "hitl.json",
    {
        "order": order,
        "before": before,
        "proposal": proposal,
        "confirmed": confirmed,
        "replay": replay,
        "after": after,
        "after_replay": replayed,
        "proposal_nodes": pt["nodes"],
    },
)
checks["hitl_sql_idempotency"] = "PASS"

# Existing tokens only, stored on native WSL filesystem with 0600 and user ownership.
private = Path("/home/panda/.local/adaptive-rag-production-20261113")
private.mkdir(parents=True, exist_ok=True, mode=0o700)
os.chown(private, 1000, 1000)
config = private / "browser-config.json"
with config.open("x") as stream:
    json.dump({"port": 8000, "tokens": tokens}, stream)
os.chmod(config, 0o600)
os.chown(config, 1000, 1000)
save(
    "offline-http-acceptance.json",
    {
        "checks": checks,
        "paid_requests": 0,
        "real_llm": "NOT_RUN",
        "production_dependency_outage_injected": False,
        "browser_config_private": str(config),
    },
)
print(json.dumps({"checks": checks, "paid_requests": 0, "browser_config_permissions": "0600"}))
