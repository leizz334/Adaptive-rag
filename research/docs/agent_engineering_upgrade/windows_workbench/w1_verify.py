"""W1 isolated HTTP/SQL evidence; run under WSL with Python's standard library.

Creates only a NEW explicitly named project. Never rebuilds, stops, deletes, or
recreates preexisting containers. Leaves owned volumes and stack for W4 reuse.
Credentials and subprocess logs remain in the ignored .private directory.
"""

import argparse
import json
import os
import re
import socket
import subprocess
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SERVICES = {"api", "bootstrap", "initialize", "postgres", "redis", "qdrant"}
LABEL = "io.adaptive-rag.showcase"
QUESTION = "定制商品过了七天，但有质量问题还能退吗？"


class Verification:
    def __init__(self, project, port, create):
        if not re.fullmatch(r"adaptive-rag-w1-[a-z0-9-]+", project):
            raise ValueError("explicit owned W1 project name required")
        if not 1024 <= port <= 65535:
            raise ValueError("invalid port")
        self.project, self.port = project, port
        self.private = HERE / ".private" / project
        self.output = HERE / "evidence" / project
        self.private.mkdir(parents=True, exist_ok=not create)
        self.output.mkdir(parents=True, exist_ok=not create)
        self.override = self.private / "compose.override.json"
        self.compose = [
            "docker",
            "compose",
            "-p",
            project,
            "-f",
            str(ROOT / "compose.showcase.yml"),
            "-f",
            str(self.override),
        ]
        self.env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
        self.env["SHOWCASE_PORT"] = str(port)
        self.stage = "setup"
        self.counter = 0
        self.tokens = {}
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def save(self, name, value, private=False):
        path = (self.private if private else self.output) / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def run(self, args, timeout=120):
        result = subprocess.run(
            args, cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode:
            self.save(
                "command-failure.json",
                {
                    "stage": self.stage,
                    "argv": args,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
                True,
            )
            raise RuntimeError("command failed; diagnostics private")
        return result.stdout

    def containers(self, project):
        ids = self.run(
            ["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + project]
        ).split()
        rows = json.loads(self.run(["docker", "inspect", *ids])) if ids else []
        return [
            {
                "id": r["Id"],
                "name": r["Name"],
                "image": r["Image"],
                "status": r["State"]["Status"],
                "started_at": r["State"]["StartedAt"],
                "service": r["Config"]["Labels"].get("com.docker.compose.service"),
                "project": r["Config"]["Labels"].get("com.docker.compose.project"),
                "ownership": r["Config"]["Labels"].get(LABEL),
                "config_files": r["Config"]["Labels"].get(
                    "com.docker.compose.project.config_files"
                ),
                "working_dir": r["Config"]["Labels"].get("com.docker.compose.project.working_dir"),
                "ports": r["HostConfig"].get("PortBindings"),
                "mounts": [
                    {"type": m["Type"], "name": m.get("Name"), "destination": m["Destination"]}
                    for m in r["Mounts"]
                ],
            }
            for r in rows
        ]

    def guard(self):
        rows = self.containers(self.project)
        assert {r["service"] for r in rows} == SERVICES, "incomplete owned project"
        for row in rows:
            assert row["project"] == self.project and row["ownership"] == "s1-docker-v1"
            assert row["working_dir"] == str(ROOT)
            assert row["config_files"] == str(ROOT / "compose.showcase.yml") + "," + str(
                self.override
            )
            assert all(
                m["type"] != "volume" or m["name"].startswith(self.project + "_")
                for m in row["mounts"]
            )
            if row["service"] == "api":
                assert row["ports"]["8000/tcp"] == [
                    {"HostIp": "127.0.0.1", "HostPort": str(self.port)}
                ]
        return rows

    def create(self):
        self.stage = "identity_checked_create"
        assert not self.containers(self.project), "project already exists"
        for kind in ["volume", "network"]:
            assert not self.run(
                [
                    "docker",
                    kind,
                    "ls",
                    "-q",
                    "--filter",
                    "label=com.docker.compose.project=" + self.project,
                ]
            ).strip()
            names = self.run(["docker", kind, "ls", "--format", "{{.Name}}"]).splitlines()
            assert not any(
                n.startswith(self.project + "_") for n in names
            ), "preexisting name collision"
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", self.port))
        for service in ["api", "bootstrap", "initialize"]:
            self.run(["docker", "image", "inspect", "adaptive-rag-showcase-" + service])
        self.save("user_stack_before.json", self.containers("adaptive-rag-showcase"))
        self.override.write_text(
            json.dumps(
                {
                    "services": {
                        s: {"image": "adaptive-rag-showcase-" + s, "pull_policy": "never"}
                        for s in ["api", "bootstrap", "initialize"]
                    }
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        result = self.run(self.compose + ["up", "-d", "--no-build", "--pull", "never"], timeout=240)
        (self.private / "compose-up.log").write_text(result, encoding="utf-8")
        self.guard()
        self.save(
            "reuse.json",
            {
                "project": self.project,
                "port": self.port,
                "base_url": f"http://127.0.0.1:{self.port}",
                "source": str(ROOT),
                "override_private": str(self.override),
                "credential_private": str(self.private / "development_credentials.json"),
                "compose_argv": self.compose,
                "leave_running_for": "W4",
                "reserved_orders": ["ORD95102", "ORD95104"],
            },
        )

    def request(self, method, path, data=None, subject="a", expected=200, stream=False):
        headers = {"Authorization": "Bearer " + self.tokens[subject]} if self.tokens else {}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/v1" + path,
            data=json.dumps(data).encode() if data is not None else None,
            headers=headers,
            method=method,
        )
        try:
            response = self.http.open(request, timeout=45)
        except urllib.error.HTTPError as exc:
            response = exc
        body = response.read().decode()
        self.counter += 1
        parsed = (
            [json.loads(line[5:]) for line in body.splitlines() if line.startswith("data:")]
            if stream
            else json.loads(body)
        )
        self.save(
            f"http-{self.counter:03d}.json",
            {"method": method, "path": path, "status": response.status, "body": parsed},
            True,
        )
        assert response.status == expected, f"HTTP {response.status} at {path}; expected {expected}"
        return parsed

    def sql(self, query):
        assert query.startswith("SELECT "), "read-only SQL only"
        return json.loads(
            self.run(
                self.compose
                + [
                    "exec",
                    "-T",
                    "postgres",
                    "psql",
                    "-X",
                    "-U",
                    "adaptive",
                    "-d",
                    "adaptive_showcase",
                    "-At",
                    "-c",
                    query,
                ]
            )
        )

    def snapshot(self):
        return {
            "orders": self.sql(
                "SELECT json_agg(x ORDER BY order_id) FROM (SELECT order_id,status,total_cents FROM orders WHERE order_id LIKE 'ORD95%') x"
            ),
            "audit": self.sql(
                "SELECT coalesce(json_agg(x ORDER BY id),'[]'::json) FROM (SELECT id,action,trace_id FROM audit_logs) x"
            ),
            "idempotency_count": self.sql("SELECT to_json(count(*)) FROM idempotency_keys"),
        }

    def trace(self, answer):
        trace = self.request(
            "GET", f"/sessions/{answer['session_id']}/traces/{answer['root_run_id']}"
        )
        self.save("trace-" + answer["root_run_id"] + ".json", trace)
        return trace

    def ready(self):
        self.stage = "readiness"
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                self.run(
                    self.compose
                    + ["exec", "-T", "api", "python", "-m", "app.demo.docker", "health"],
                    timeout=15,
                )
                break
            except (RuntimeError, subprocess.TimeoutExpired):
                time.sleep(2)
        else:
            raise RuntimeError("readiness timeout")
        credentials = json.loads(
            self.run(
                self.compose
                + ["exec", "-T", "api", "cat", "/var/lib/showcase/development_credentials.json"]
            )
        )
        self.tokens = credentials["tokens"]
        self.save("development_credentials.json", credentials, True)
        self.save("browser-config.json", {"port": self.port, "tokens": self.tokens}, True)

    def verify(self):
        self.guard()
        self.ready()
        self.stage = "baseline"
        initial = self.snapshot()
        self.save("initial_database.json", initial)
        assert all(
            r["status"] == "paid" for r in initial["orders"]
        ), "requires unused fresh fixture"
        baseline = self.request("POST", "/chat", {"message": QUESTION})
        baseline_trace = self.trace(baseline)
        assert (
            baseline["intent"] == "return_exchange"
            and not baseline["citations"]
            and not baseline_trace["retrieval"]
        )
        assert baseline["token_usage"]["total_tokens"] == 0
        self.save(
            "question_before_seed.json",
            {
                "question": QUESTION,
                "response": baseline,
                "cause": "Private knowledge empty; no automatic ingestion of public knowledge/. Offline no-evidence fallback.",
            },
        )

        self.stage = "multi_turn_http_sse_memory"
        first = self.request("POST", "/chat", {"message": "请查询 ORD95101 的订单状态和金额"})
        first_trace = self.trace(first)
        assert "68" in first["answer"]
        assert any(
            t["name"] == "get_order" and t["result"].get("total_cents") == 6800
            for t in first_trace["tools"]
        )
        events = self.request(
            "POST",
            "/chat/stream",
            {"message": "这单的商品明细和是否定制也帮我核实", "session_id": first["session_id"]},
            stream=True,
        )
        assert not any(e["event"] == "error" for e in events)
        second = next(e["data"] for e in events if e["event"] == "answer")
        second_trace = self.trace(second)
        assert second["session_id"] == first["session_id"] and "演示帆布包" in second["answer"]
        assert (
            second_trace["memory"]["message_count"] > 0 and second_trace["memory"]["mode"] == "M2"
        )
        assert any(
            t["name"] == "get_order_items" and t["result"].get("item_count") == 1
            for t in second_trace["tools"]
        )
        history = self.request("GET", f"/sessions/{first['session_id']}/messages")
        assert len(history["messages"]) == 4
        self.request("GET", f"/sessions/{first['session_id']}/messages", subject="b", expected=404)
        self.save(
            "multi_turn.json",
            {
                "http": first,
                "sse_answer": second,
                "sse_events": [e["event"] for e in events],
                "memory": second_trace["memory"],
                "history_messages": len(history["messages"]),
                "owner_b_history_status": 404,
            },
        )

        self.stage = "private_knowledge_owner_isolation"
        document = "w1-synthetic-quality-policy"
        content = "# 合成演示退货政策\n定制商品过了七天，但有质量问题还能退吗？定制商品不适用七天无理由退货；如存在质量问题，超过七天仍可申请售后退换，须提供合成订单和质量证明，最终按审核处理。本段仅供隔离演示，并非真实商家政策。"
        upload = self.request(
            "POST",
            "/knowledge/documents/" + document,
            {"title": "合成演示退货政策", "content": content},
        )
        own = self.request("POST", "/knowledge/search", {"query": QUESTION, "mode": "hybrid"})
        foreign = self.request(
            "POST", "/knowledge/search", {"query": QUESTION, "mode": "hybrid"}, subject="b"
        )
        assert document in {c["document_id"] for c in own["chunks"]}
        assert not foreign["chunks"]
        assert document not in {
            d["document_id"]
            for d in self.request("GET", "/knowledge/documents", subject="b")["documents"]
        }
        self.request("DELETE", "/knowledge/documents/" + document, subject="b", expected=404)
        grounded = self.request("POST", "/chat", {"message": QUESTION})
        grounded_trace = self.trace(grounded)
        assert document in {c["document_id"] for c in grounded["citations"]}
        assert any(
            c["document_id"] == document and "质量问题" in c["excerpt"]
            for c in grounded_trace["retrieval"]
        )
        assert "质量问题" in grounded["answer"] and "超过七天" in grounded["answer"]
        self.request(
            "GET",
            f"/sessions/{grounded['session_id']}/traces/{grounded['root_run_id']}",
            subject="b",
            expected=404,
        )
        self.save(
            "private_knowledge.json",
            {
                "synthetic_only": True,
                "document": document,
                "upload": upload,
                "owner_a_search_citations": own["citations"],
                "owner_b_search_chunks": len(foreign["chunks"]),
                "owner_b_delete_status": 404,
                "owner_b_trace_status": 404,
                "response": grounded,
            },
        )

        self.stage = "hitl_idempotency_real_sql"
        before = self.snapshot()
        proposal = self.request("POST", "/chat", {"message": "请取消订单 ORD95103"})
        proposal_trace = self.trace(proposal)
        assert proposal["pending_action"]["tool_name"] == "cancel_order"
        assert (
            next(r for r in self.snapshot()["orders"] if r["order_id"] == "ORD95103")["status"]
            == "paid"
        )
        action = proposal["pending_action"]["action_id"]
        path = f"/sessions/{proposal['session_id']}/actions/{action}"
        self.request("POST", path + "/cancel", subject="b", expected=404)
        payload = {
            "message": "确认执行",
            "session_id": proposal["session_id"],
            "confirm_action_id": action,
            "idempotency_key": action,
        }
        confirmed = self.request("POST", "/chat", payload)
        after_confirm = self.snapshot()
        replay = self.request("POST", "/chat", payload)
        after_replay = self.snapshot()
        assert "已取消" in confirmed["answer"] and "已取消" in replay["answer"]
        assert after_confirm == after_replay, "replay changed business/audit/idempotency data"
        assert (
            next(r for r in after_replay["orders"] if r["order_id"] == "ORD95103")["status"]
            == "cancelled"
        )
        cancel_audits = [a for a in after_replay["audit"] if a["action"] == "cancel_order"]
        assert len(cancel_audits) == 1
        assert after_replay["idempotency_count"] == before["idempotency_count"] + 1
        status = self.request("GET", path)
        assert status["status"] == "completed"
        self.request("POST", path + "/cancel", expected=409)
        assert all(
            r["status"] == "paid"
            for r in after_replay["orders"]
            if r["order_id"] in {"ORD95102", "ORD95104"}
        )
        self.save(
            "hitl.json",
            {
                "order_id": "ORD95103",
                "proposal": proposal,
                "proposal_nodes": proposal_trace["nodes"],
                "before": before,
                "confirmed": confirmed,
                "replay": replay,
                "after_confirm": after_confirm,
                "after_replay": after_replay,
                "cancel_audit_count": len(cancel_audits),
                "action_status": status,
                "owner_b_cancel_status": 404,
                "completed_cancel_status": 409,
                "reserved_orders_unchanged": True,
            },
        )
        original = self.containers("adaptive-rag-showcase")
        assert original == json.loads(
            (self.output / "user_stack_before.json").read_text()
        ), "original stack lifecycle changed"
        self.save("user_stack_after.json", original)
        self.save(
            "acceptance.json",
            {
                "status": "PASS",
                "project": self.project,
                "port": self.port,
                "scenarios": [
                    "HTTP + SSE multi-turn Memory and order tools",
                    "private KB upload/search/citation and Owner isolation",
                    "Planner/HITL real SQL cancellation and idempotency replay",
                ],
                "exact_question_before_seed": "no evidence fallback",
                "exact_question_after_synthetic_seed": "grounded policy excerpt with citation",
                "paid_requests": 0,
                "llm": "CONTROLLED_OFFLINE_NOT_REAL_LLM",
                "original_stack_lifecycle_unchanged": True,
                "reserved_orders": ["ORD95102", "ORD95104"],
                "stack_left_running": True,
            },
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--create", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    runner = None
    try:
        runner = Verification(args.project, args.port, args.create)
        if args.create:
            runner.create()
        runner.verify()
    except Exception as exc:
        if runner:
            (runner.private / "failure.log").write_text(traceback.format_exc(), encoding="utf-8")
            runner.save(
                "failure.json", {"exception_type": type(exc).__name__, "stage": runner.stage}
            )
        print("W1 FAIL; private diagnostics preserved")
        raise SystemExit(1) from None
    print("W1 PASS; sanitized evidence saved; isolated stack remains running")


if __name__ == "__main__":
    main()
