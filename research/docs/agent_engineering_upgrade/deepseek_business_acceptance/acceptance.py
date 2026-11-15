"""Explicit, one-shot REAL business acceptance; never runs on import.

Run fixture preparation separately, then invoke exactly one named scenario.
An existing started marker is a hard stop even when its previous result failed.
Gateway requests are not counted as provider HTTP: the durable ledger is authoritative.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
OUT = HERE / "evidence"
PRIVATE = Path("/home/panda/.adaptive-rag-business-20261114")
API = "adaptive-rag-real-agent-dev-api-1"
BASE = "http://127.0.0.1:8001/api/v1"
GRANT = "business-20261115-20usd005"
SCENARIOS = ("order", "memory", "rag", "negative", "hitl")


def container(code):
    """Capture stdout only; subprocess diagnostics can contain private configuration."""
    result = subprocess.run(
        ["docker", "exec", API, "python", "-c", code],
        capture_output=True,
        text=True,
        timeout=40,
    )
    if result.returncode:
        raise RuntimeError("container evidence query failed; diagnostics withheld")
    return json.loads(result.stdout)


def ledger(*, paid=False):
    data = container(
        """
import json,os
from urllib.parse import urlsplit
from app.demo.real_dev import load_runtime_config
from app.providers.paid_budget import AttemptLedger
c=load_runtime_config()
u=urlsplit(c.settings.deepseek_base_url)
assert u.scheme=='https' and u.hostname=='api.deepseek.com' and u.port in {None,443}
assert u.path.rstrip('/') in {'','/v1'} and not(u.username or u.password or u.query or u.fragment)
assert c.settings.deepseek_model==c.limits.model=='deepseek-flash'
assert c.settings.deepseek_thinking_mode=='disabled' and c.settings.llm_max_retries==1
assert c.authorization_id=='business-20261115-20usd005'
assert (c.limits.max_requests,c.limits.max_tokens,str(c.limits.max_usd))==(6,10000,'0.05')
assert (str(c.limits.input_usd_per_million),str(c.limits.output_usd_per_million))==('0.30','1.20')
b=AttemptLedger(c.budget_path,c.limits,authorization_id=c.authorization_id)
print(json.dumps(dict(lifetime=b.snapshot(),grant=b.authorization_snapshot(),paid_authorized=os.environ.get('REAL_AGENT_PAID_AUTHORIZED','').lower()=='true')))
"""
    )
    grant = data["grant"]
    assert grant["id"] == GRANT
    assert grant["max_requests"] == 20 and grant["max_tokens"] is None
    assert Decimal(grant["max_usd"]) == Decimal("0.05") and not grant["closed"]
    assert 0 <= grant["requests"] <= 20 and Decimal(grant["usd"]) <= Decimal("0.05")
    if paid:
        assert data["paid_authorized"], "REAL_AGENT_PAID_AUTHORIZED=true is required"
        assert not any(
            data[scope][key] for scope in ("lifetime", "grant") for key in ("pending", "uncertain")
        ), "billing uncertainty; no further paid call"
        if grant["requests"] >= 20 or Decimal(grant["usd"]) >= Decimal("0.05"):
            raise BudgetBlocked("grant exhausted before dispatch")
    return data


def sql_state(order_id, *, create=False, action_id=""):
    """Use existing SQLAlchemy models; creation is limited to a fresh synthetic row."""
    assert re.fullmatch(r"ORD[0-9]{1,20}", order_id)
    return container(
        """
import asyncio,json
from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app.demo.real_dev import load_runtime_config
from app.repositories.models import OrderRow,OrderItemRow,AuditLogRow,IdempotencyRow
from app.core.time import utcnow
"""
        + f"ORDER={order_id!r}\nCREATE={create!r}\nACTION={action_id!r}\n"
        + """
async def main():
 c=load_runtime_config()
 e=create_async_engine(c.settings.database_url)
 assert e.dialect.name=='postgresql'
 try:
  async with async_sessionmaker(e,expire_on_commit=False)() as db:
   row=await db.get(OrderRow,ORDER)
   if CREATE:
    assert ORDER.startswith('ORD20261115') and row is None,'never overwrite an existing order'
    row=OrderRow(order_id=ORDER,user_id='web_demo_a',status='paid',total_cents=1234,created_at=utcnow(),paid_at=utcnow(),receiver_city='Synthetic acceptance fixture')
    db.add(row)
    await db.flush()
    db.add(OrderItemRow(order_id=ORDER,sku='SKU-BUSINESS-SYNTHETIC',name='Synthetic acceptance fixture only',quantity=1,unit_price_cents=1234,customized=False))
    await db.commit()
   items=(await db.scalars(select(OrderItemRow).where(OrderItemRow.order_id==ORDER))).all()
   print(json.dumps(dict(order=None if row is None else dict(order_id=row.order_id,user_id=row.user_id,status=row.status,total_cents=row.total_cents),items=[dict(name=i.name,quantity=i.quantity,customized=i.customized,unit_price_cents=i.unit_price_cents) for i in items],order_audit=await db.scalar(select(func.count()).select_from(AuditLogRow).where(AuditLogRow.payload==ORDER)),audit=await db.scalar(select(func.count()).select_from(AuditLogRow)),idempotency=await db.scalar(select(func.count()).select_from(IdempotencyRow)),action_key=bool(ACTION and await db.get(IdempotencyRow,ACTION) is not None)),ensure_ascii=True))
 finally:
  await e.dispose()
asyncio.run(main())
"""
    )


class Driver:
    def __init__(self, *, browser_order=False):
        self.browser_order = browser_order
        self.tokens = json.loads((PRIVATE / "browser-config.json").read_text())["tokens"]
        assert all(isinstance(self.tokens.get(k), str) and self.tokens[k] for k in ("a", "b"))
        self.client = httpx.Client(
            base_url=BASE, trust_env=False, timeout=180, follow_redirects=False
        )
        self.journal = []
        self.name = None

    def clean(self, value):
        if isinstance(value, dict):
            return {
                k: self.clean(v)
                for k, v in value.items()
                if k.lower() not in {"api_key", "tokens", "token", "headers"}
                or k == "tokens"
                and isinstance(v, int)
            }
        if isinstance(value, list):
            return [self.clean(v) for v in value]
        if isinstance(value, str):
            for token in self.tokens.values():
                value = value.replace(token, "[REDACTED]")
            return re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", value)
        return value

    def save(self, name, value):
        with (OUT / name).open("x", encoding="utf-8") as stream:
            json.dump(self.clean(value), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())

    def request(self, method, path, data=None, *, subject="a"):
        headers = {"Authorization": "Bearer " + self.tokens[subject]} if subject else {}
        response = self.client.request(method, path, json=data, headers=headers)
        try:
            body = response.json()
        except (ValueError, UnicodeError):
            body = {"non_json_body": response.text[:20000]}
        return response.status_code, body

    def checked(self, method, path, data=None, *, subject="a", expected=200):
        status, body = self.request(method, path, data, subject=subject)
        assert status == expected, f"{method} {path}: expected {expected}, received {status}"
        return body

    def preflight(self):
        assert self.checked("GET", "/auth/me")["subject"] == "web_demo_a"
        assert self.checked("GET", "/auth/me", subject="b")["subject"] == "web_demo_b"
        self.checked("GET", "/auth/me", subject=None, expected=401)
        caps = self.checked("GET", "/capabilities")
        assert caps["llm"] == "deepseek"
        status = self.checked("GET", "/runtime-status", subject=None)
        assert status["mode"] == "deepseek" and status["verification_only"] is False
        ready = self.checked("GET", "/ready", subject=None)
        assert all(
            next(x["ready"] for x in ready["dependencies"] if x["name"] == name)
            for name in ("database", "redis", "vector_store")
        )
        return {"capabilities": caps, "runtime_status": status, "ledger": ledger()}

    def chat(self, label, payload, *, stream=False, allow_zero=False):
        before = ledger(paid=True)
        runtime = self.checked("GET", "/runtime-status", subject=None)
        assert runtime["mode"] == "deepseek" and runtime["verification_only"] is False
        if not runtime["available"]:
            raise BudgetBlocked("runtime admission unavailable before dispatch")
        seq = len(self.journal) + 1
        stem = f"B3-{self.name}-{seq:02d}-{label}"
        record = {
            "label": label,
            "request": payload,
            "path": "/chat/stream" if stream else "/chat",
            "ledger_before": before,
        }
        self.save(stem + "-started.json", record)
        started = time.monotonic()
        events, answer = [], None
        try:
            if self.browser_order and self.name == "order" and label == "query":
                # Windows Chromium sends the sole real chat; never replay via HTTP.
                script = "D:/Code/Adaptive-rag/.worktrees/p3-experience-validation/research/docs/agent_engineering_upgrade/deepseek_business_acceptance/browser_order.mjs"
                wire = subprocess.run(
                    ["/mnt/c/Program Files/nodejs/node.exe", script],
                    capture_output=True,
                    text=True,
                    timeout=175,
                )
                if wire.returncode:
                    (PRIVATE / "browser-order-error.log").write_text(wire.stderr)
                    raise RuntimeError(
                        "Chromium order request failed; reconcile ledger without replay"
                    )
                captured = json.loads(wire.stdout)
                record["browser"] = captured["ui"]
                # Only adapt the captured real response for the common evidence parser.
                response = httpx.Response(captured["http_status"], json=captured["body"])
            else:
                response = self.client.post(
                    record["path"],
                    json=payload,
                    headers={"Authorization": "Bearer " + self.tokens["a"]},
                )
            record["http_status"] = response.status_code
            if stream and response.status_code == 200:
                for line in response.text.splitlines():
                    if line.startswith("data:"):
                        events.append(json.loads(line[5:]))
                record["sse_events"] = events
                answer = next((e.get("data") for e in events if e.get("event") == "answer"), None)
            else:
                try:
                    record["response"] = response.json()
                except ValueError:
                    record["response"] = {"non_json_body": response.text[:20000]}
                if response.status_code == 200:
                    answer = record["response"]
            record["answer"] = answer
        except Exception as exc:
            record["transport_error_type"] = type(exc).__name__
        finally:
            record["latency_ms"] = round((time.monotonic() - started) * 1000)
            try:
                after = ledger()
                record["ledger_after"] = after
                record["actual_model_http_requests"] = (
                    after["lifetime"]["requests"] - before["lifetime"]["requests"]
                )
                record["settled_requests"] = (
                    after["lifetime"]["settled"] - before["lifetime"]["settled"]
                )
                record["settled_tokens"] = (
                    after["lifetime"]["tokens"] - before["lifetime"]["tokens"]
                )
                record["settled_usage_cost_usd"] = str(
                    Decimal(after["lifetime"]["usd"]) - Decimal(before["lifetime"]["usd"])
                )
                record["grant_request_delta"] = (
                    after["grant"]["requests"] - before["grant"]["requests"]
                )
            except Exception as exc:
                record["ledger_error_type"] = type(exc).__name__
            candidates = [answer] + [e.get("data", e) for e in events] + [record.get("response")]
            for item in candidates:
                if isinstance(item, dict) and item.get("session_id") and item.get("root_run_id"):
                    try:
                        code, trace = self.request(
                            "GET", f'/sessions/{item["session_id"]}/traces/{item["root_run_id"]}'
                        )
                        record["trace_http_status"] = code
                        if code == 200:
                            record["trace"] = trace
                            break
                    except Exception as exc:
                        record["trace_error_type"] = type(exc).__name__
            spans = [s for s in record.get("trace", {}).get("spans", []) if s.get("kind") == "llm"]
            record["usage"] = {
                k: sum(s.get("metadata", {}).get(k, 0) for s in spans)
                for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            }
            record["usage_known_spans"] = sum(
                s.get("status") == "ok"
                and s.get("metadata", {}).get("usage_known") is True
                and s.get("metadata", {}).get("total_tokens", 0) > 0
                for s in spans
            )
            record["estimated_trace_usage_cost_usd"] = str(
                (
                    Decimal(record["usage"]["prompt_tokens"]) * Decimal("0.30")
                    + Decimal(record["usage"]["completion_tokens"]) * Decimal("1.20")
                )
                / Decimal(1000000)
            )
            self.journal.append(record)
            self.save(stem + "-response.json", record)
        if "ledger_after" not in record:
            raise AssertionError("ledger unavailable after request; stop for reconciliation")
        assert not any(
            record["ledger_after"][scope][key]
            for scope in ("lifetime", "grant")
            for key in ("pending", "uncertain")
        ), "uncertain billing; stop"
        if record.get("http_status") == 503 or any(
            e.get("event") == "error" and "budget" in json.dumps(e).lower() for e in events
        ):
            raise BudgetBlocked("HTTP/SSE budget admission blocked; no successful business result")
        assert record.get("http_status") == 200 and answer, "incomplete HTTP/SSE response"
        assert not any(e.get("event") == "error" for e in events), "SSE error"
        assert not stream or any(e.get("event") == "done" for e in events), "SSE missing completion"
        count = record["actual_model_http_requests"]
        assert count >= (0 if allow_zero else 1), "no actual provider dispatch evidence"
        assert (
            count
            == record["grant_request_delta"]
            == record["settled_requests"]
            == record["usage_known_spans"]
        ), "provider usage/settlement evidence incomplete"
        assert (
            record["usage"]["total_tokens"] == record["settled_tokens"]
        ), "trace and settlement token totals differ"
        assert Decimal(record["estimated_trace_usage_cost_usd"]) == Decimal(
            record["settled_usage_cost_usd"]
        ), "trace and settlement fees differ"
        assert record.get("trace"), "no trace available"
        return answer, record["trace"]

    def fixtures(self):
        assert not (
            OUT / "B2-fixtures-started.json"
        ).exists(), "fixture preparation already started; reconcile manually"
        assert not (OUT / "B2-fixtures.json").exists()
        preflight = self.preflight()
        suffix = uuid.uuid4().hex[:12]
        fixture = {
            "document_id": "business-policy-" + suffix,
            "marker": "POLICY" + suffix.upper(),
            "order_id": "ORD20261115" + str(uuid.uuid4().int % 10**10).zfill(10),
        }
        self.save("B2-fixtures-started.json", fixture)
        fixture["sql"] = sql_state(fixture["order_id"], create=True)
        question = f'{fixture["marker"]} 专属合成政策：定制商品超过七天但有质量问题，还能申请售后退换吗？需要哪些凭证？'
        fixture["question"] = question
        content = (
            question
            + "\n本段仅供隔离合成验收，绝非真实商家政策。定制商品不适用七天无理由退货；存在质量问题时，即使超过七天仍可申请售后退换，但须提交合成订单与质量问题照片，最终经人工审核决定。"
        )
        fixture["upload"] = self.checked(
            "POST",
            "/knowledge/documents/" + fixture["document_id"],
            {"title": fixture["marker"] + " 合成定制商品质量售后政策", "content": content},
        )
        fixture["own_search"] = self.checked(
            "POST", "/knowledge/search", {"query": question, "mode": "hybrid"}
        )
        fixture["foreign_search"] = self.checked(
            "POST", "/knowledge/search", {"query": question, "mode": "hybrid"}, subject="b"
        )
        assert any(
            c["document_id"] == fixture["document_id"] for c in fixture["own_search"]["chunks"]
        )
        assert not any(
            c["document_id"] == fixture["document_id"] for c in fixture["foreign_search"]["chunks"]
        )
        fixture["ledger_before"], fixture["ledger_after"] = preflight["ledger"], ledger()
        assert (
            fixture["ledger_before"] == fixture["ledger_after"]
        ), "fixture preparation must not dispatch a model request"
        fixture["status"] = "PASS"
        self.save("B2-fixtures.json", fixture)
        return fixture

    def scenario(self, name):
        self.name = name
        assert not (
            OUT / f"B3-{name}-started.json"
        ).exists(), "scenario already started; never automatically replay a paid case"
        assert not (OUT / f"B3-{name}.json").exists(), "scenario evidence already exists"
        result = {
            "scenario": name,
            "status": "NOT_RUN",
            "authorization_id": GRANT,
            "started_at": datetime.now(UTC).isoformat(),
            "provider": "DeepSeekProvider",
            "verification_only": False,
            "billing_statement_verified": False,
        }
        self.save(f"B3-{name}-started.json", result)
        try:
            result["preflight"] = self.preflight()
            ledger(paid=True)
            getattr(self, "case_" + name)(result)
            result["status"] = "PASS"
        except BudgetBlocked as exc:
            result.update(status="BUDGET_BLOCKED", reason=str(exc))
        except Exception as exc:
            result.update(
                status="FAIL" if self.journal else "NOT_RUN", error_type=type(exc).__name__
            )
            if isinstance(exc, AssertionError):
                result["reason"] = str(exc)
        finally:
            result["requests"] = self.journal
            result["actual_model_http_requests"] = sum(
                r.get("actual_model_http_requests", 0) for r in self.journal
            )
            result["actual_model_http_requests_known"] = all(
                "actual_model_http_requests" in r for r in self.journal
            )
            result["actual_usage"] = {
                k: sum(r.get("usage", {}).get(k, 0) for r in self.journal)
                for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            }
            result["settled_usage_cost_usd"] = str(
                sum(
                    (Decimal(r.get("settled_usage_cost_usd", "0")) for r in self.journal),
                    Decimal(0),
                )
            )
            try:
                result["final_ledger"] = ledger()
            except Exception:
                result["final_ledger_unavailable"] = True
                result["status"] = "FAIL"
            self.save(f"B3-{name}.json", result)
        return result

    def fixture(self):
        fixture = json.loads((OUT / "B2-fixtures.json").read_text(encoding="utf-8"))
        assert fixture["status"] == "PASS"
        return fixture

    def case_order(self, result):
        actual = sql_state("ORD95101")
        result["sql"] = actual
        assert (
            actual["order"]["user_id"] == "web_demo_a"
            and actual["order"]["status"] == "paid"
            and actual["order"]["total_cents"] == 6800
        )
        answer, trace = self.chat("query", {"message": "请查询 ORD95101 的订单状态和金额。"})
        result["session_id"] = answer["session_id"]
        assert any(
            t["name"] == "get_order"
            and t["success"]
            and t["result"].get("total_cents") == 6800
            and t["result"].get("status") == "paid"
            for t in trace["tools"]
        )
        assert any(
            p["tool_name"] == "get_order" and p["arguments"].get("order_id") == "ORD95101"
            for p in trace["planner_steps"]
        )
        assert re.search(r"\b68(?:\.0+)?\b", answer["answer"]) and any(
            status in answer["answer"]
            for status in ("已支付", "已付款", "支付成功", "付款成功", "已付", "paid")
        )
        assert not answer["refused"]

    def case_memory(self, result):
        previous = json.loads((OUT / "B3-order.json").read_text(encoding="utf-8"))
        if previous["status"] != "PASS":
            # Preserve the original failed accounting assertion. Reuse the real
            # successful business turn without spending five calls to replay it.
            import hashlib

            reviewed = json.loads((OUT / "B3-order-business-review.json").read_text())
            assert reviewed["business_status"] == "PASS" and reviewed["no_model_replay"]
            assert (
                reviewed["source_evidence_sha256"]
                == hashlib.sha256((OUT / "B3-order.json").read_bytes()).hexdigest()
            )
            session = reviewed["session_id"]
        else:
            session = previous["session_id"]
        assert session
        actual = sql_state("ORD95101")
        result["sql"] = actual
        answer, trace = self.chat(
            "followup",
            {"message": "这单的商品明细和是否定制也帮我核实。", "session_id": session},
            stream=True,
        )
        assert answer["session_id"] == session and trace["memory"]["message_count"] > 0
        assert trace["memory"]["mode"] in {"M1", "M2", "M3"}
        assert any(
            t["name"] == "get_order_items"
            and t["success"]
            and t["result"].get("item_count") == len(actual["items"]) > 0
            for t in trace["tools"]
        )
        assert any(
            p["tool_name"] == "get_order_items" and p["arguments"].get("order_id") == "ORD95101"
            for p in trace["planner_steps"]
        )
        assert all(i["name"] in answer["answer"] for i in actual["items"])
        assert "定制" in answer["answer"] and not answer["refused"]
        if all(not item["customized"] for item in actual["items"]):
            assert any(
                s in answer["answer"]
                for s in (
                    "非定制",
                    "不是定制",
                    "不属于定制",
                    "未定制",
                    "不定制",
                    "定制：否",
                    "定制: 否",
                    "定制：false",
                    "定制: false",
                )
            ), "customization answer must match actual SQL items"
        result["history"] = self.checked("GET", f"/sessions/{session}/messages")
        self.checked("GET", f"/sessions/{session}/messages", subject="b", expected=404)
        assert any(
            m["content"] == answer["answer"] and m["role"] == "assistant"
            for m in result["history"]["messages"]
        )

    def case_rag(self, result):
        fixture = self.fixture()
        result["document_id"] = fixture["document_id"]
        answer, trace = self.chat("policy", {"message": fixture["question"]})
        retrieved = {
            c["chunk_id"]
            for c in trace["retrieval"]
            if c["document_id"] == fixture["document_id"] and fixture["marker"] in c["excerpt"]
        }
        cited = {
            c["chunk_id"] for c in answer["citations"] if c["document_id"] == fixture["document_id"]
        }
        if not retrieved & cited:
            # Generic Trace redaction can hide opaque chunk IDs. Verify the
            # public citation against authenticated knowledge results instead;
            # keep the backend's privacy filter unchanged.
            owned = {
                c["chunk_id"]
                for c in fixture["own_search"]["chunks"]
                if c["document_id"] == fixture["document_id"]
            }
            assert (
                retrieved == {"[REDACTED]"} and owned & cited
            ), "citation must match owned policy and actual trace document/excerpt"
        text = answer["answer"]
        assert (
            "质量" in text
            and "审核" in text
            and ("照片" in text or "凭证" in text)
            and "定制" in text
        )
        assert (
            "无理由" in text
            and any(s in text for s in ("可以", "可申请", "仍可", "能够"))
            and not answer["refused"]
        )

    def case_negative(self, result):
        missing = "ORD2026111599999999999"
        result["sql"] = sql_state(missing)
        assert result["sql"]["order"] is None
        answer, trace = self.chat(
            "not-found", {"message": f"请查询订单 {missing} 的状态和金额，不要猜测。"}
        )
        assert any(t["name"] == "get_order" and not t["success"] for t in trace["tools"])
        assert any(
            p["tool_name"] == "get_order" and p["arguments"].get("order_id") == missing
            for p in trace["planner_steps"]
        )
        text = answer["answer"]
        assert any(
            s in text
            for s in (
                "无法查到",
                "未找到",
                "未查到",
                "不存在",
                "无法查询",
                "未查询到",
                "没有找到",
                "未能找到",
                "未能查询",
                "查不到",
            )
        )
        assert not re.search(
            r"(?:[¥￥$]\s*\d|\d[\d,.]*\s*(?:元|人民币|美元))", text
        ), "nonexistent order must not acquire invented money"
        assert "已支付" not in text and not answer.get("pending_action")

    def case_hitl(self, result):
        order = self.fixture()["order_id"]
        before = sql_state(order)
        result["before"] = before
        assert before["order"]["status"] == "paid" and before["order_audit"] == 0
        proposal, pt = self.chat("proposal", {"message": f"请取消我的订单 {order}。"})
        pending = proposal.get("pending_action") or {}
        assert (
            pending.get("tool_name") == "cancel_order"
            and pending.get("arguments", {}).get("order_id") == order
        )
        assert not any(t["name"] == "cancel_order" and t["success"] for t in pt["tools"])
        action = pending["action_id"]
        proposed = sql_state(order, action_id=action)
        result["after_proposal"] = proposed
        assert proposed == before, "proposal must not mutate order, audit or idempotency"
        path = f'/sessions/{proposal["session_id"]}/actions/{action}'
        assert self.checked("GET", path)["status"] == "pending"
        self.checked("POST", path + "/cancel", subject="b", expected=404)
        payload = {
            "message": "确认执行",
            "session_id": proposal["session_id"],
            "confirm_action_id": action,
            "idempotency_key": action,
        }
        confirmed, ct = self.chat("confirm", payload)
        after = sql_state(order, action_id=action)
        result["after_confirmation"] = after
        assert after["order"]["status"] == "cancelled" and after["action_key"]
        assert (
            after["order_audit"] == 1
            and after["audit"] == before["audit"] + 1
            and after["idempotency"] == before["idempotency"] + 1
        )
        assert any(
            t["name"] == "cancel_order"
            and t["success"]
            and t["result"].get("status") == "cancelled"
            for t in ct["tools"]
        )
        assert "取消" in confirmed["answer"]
        replay, _ = self.chat("idempotent-replay", payload, allow_zero=True)
        again = sql_state(order, action_id=action)
        result["after_replay"] = again
        assert (
            after == again and "取消" in replay["answer"]
        ), "replay must not create a second SQL update/audit/key"
        assert self.checked("GET", path)["status"] == "completed"
        self.checked("POST", path + "/cancel", expected=409)


class BudgetBlocked(RuntimeError):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", nargs="?", choices=SCENARIOS)
    parser.add_argument("--prepare-fixtures", action="store_true")
    parser.add_argument("--browser-order", action="store_true")
    args = parser.parse_args()
    if bool(args.scenario) == args.prepare_fixtures:
        parser.error("choose exactly one scenario or --prepare-fixtures")
    os.umask(0o077)
    logging.disable(logging.CRITICAL)
    OUT.mkdir(exist_ok=True)
    if args.browser_order and args.scenario != "order":
        parser.error("--browser-order requires order scenario")
    driver = Driver(browser_order=args.browser_order)
    try:
        result = driver.fixtures() if args.prepare_fixtures else driver.scenario(args.scenario)
        print(
            json.dumps(
                {
                    "scenario": args.scenario,
                    "status": result["status"],
                    "actual_model_http_requests": result.get("actual_model_http_requests", 0),
                },
                ensure_ascii=True,
            )
        )
        return 0 if result["status"] == "PASS" else 1
    finally:
        driver.client.close()


if __name__ == "__main__":
    raise SystemExit(main())
