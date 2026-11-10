"""Actual TCP client/owned Uvicorn processes and PostgreSQL state snapshots for B3."""

import asyncio
import json
import os
import secrets
import subprocess
import sys
import time
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.repositories.models import Base

from .manage import HERE, ROOT, git, save, sha
from .sandbox import command, free_port, live_config
from .worker import TOKENS


async def snapshot(cfg):
    engine = create_async_engine(cfg["database_url"])
    try:
        async with engine.connect() as conn:
            return {
                table.name: [dict(r) for r in (await conn.execute(select(table))).mappings()]
                for table in Base.metadata.sorted_tables
            }
    finally:
        await engine.dispose()


class LiveApi:
    def __init__(self, run_id):
        if not run_id or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in run_id
        ):
            raise ValueError("unique bounded run ID required")
        self.manifest, self.cfg = live_config()
        command(self.manifest, "ps")
        self.directory = HERE / "runs" / run_id
        self.directory.mkdir(exist_ok=False)
        self.processes = []
        self.sequence = 0

    def start(self, count=2):
        self.client = httpx.Client(timeout=20, trust_env=False)
        for index in range(count):
            directory = self.directory / f"worker_{index}"
            directory.mkdir()
            port, token = free_port(), secrets.token_hex(24)
            env = {
                k: v
                for k, v in os.environ.items()
                if k
                in {
                    "PATH",
                    "HOME",
                    "LANG",
                    "CONDA_PREFIX",
                    "VIRTUAL_ENV",
                    "LD_LIBRARY_PATH",
                    "SYSTEMROOT",
                    "TEMP",
                    "TMP",
                    "P4B_RUN_LIVE",
                    "P4B_MANIFEST",
                }
            }
            env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", P4_CONTROL_TOKEN=token)
            out = (directory / "stdout.log").open("wb")
            err = (directory / "stderr.log").open("wb")
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    __package__ + ".live_worker",
                    "--run-dir",
                    str(directory),
                    "--port",
                    str(port),
                ],
                cwd=ROOT,
                env=env,
                stdout=out,
                stderr=err,
            )
            row = dict(
                process=process,
                directory=directory,
                token=token,
                url=f"http://127.0.0.1:{port}",
                out=out,
                err=err,
            )
            self.processes.append(row)
            for _ in range(300):
                if process.poll() is not None:
                    raise RuntimeError("Owned live worker failed; inspect retained private logs")
                try:
                    if (
                        self.client.get(row["url"] + "/api/v1/health").status_code == 200
                        and (directory / "startup.json").exists()
                    ):
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                raise TimeoutError("Owned live worker startup exceeded 30s")
        save(
            self.directory / "config.json",
            dict(
                head=git("rev-parse", "HEAD"),
                platform=sys.platform,
                python=sys.executable,
                project=self.cfg["project"],
                real_dependencies=True,
                real_llm=False,
                paid_requests=0,
                active=False,
                source_hashes={
                    p.relative_to(ROOT).as_posix(): sha(p) for p in (ROOT / "app").rglob("*.py")
                },
                runner_sha256=sha(__file__),
            ),
        )
        return self

    def request(
        self,
        case,
        payload=None,
        *,
        path="/api/v1/chat",
        method="POST",
        worker=0,
        identity="user",
        fault="none",
        expected=None,
    ):
        self.sequence += 1
        trace = "p4b_" + uuid.uuid4().hex
        headers = {"x-trace-id": trace, "x-p4-case": case, "x-p4-fault": fault}
        if identity:
            headers["authorization"] = "Bearer " + TOKENS[identity]
        row = dict(
            case=case,
            worker=worker,
            trace_id=trace,
            database_before=None,
            database_after=None,
            event_capture_errors=[],
        )
        try:
            row["database_before"] = asyncio.run(snapshot(self.cfg))
        except Exception as exc:
            row["snapshot_before_error"] = type(exc).__name__
        try:
            response = self.client.request(
                method, self.processes[worker]["url"] + path, json=payload, headers=headers
            )
            row.update(status=response.status_code, text=response.text, transport_error=None)
            try:
                row["body"] = response.json()
            except ValueError:
                row["body"] = None
        except httpx.TransportError as exc:
            row.update(status=None, transport_error=type(exc).__name__)
            raise
        finally:
            try:
                row["database_after"] = asyncio.run(snapshot(self.cfg))
            except Exception as exc:
                row["snapshot_after_error"] = type(exc).__name__
            events = []
            for p in self.processes:
                path_events = p["directory"] / "events.jsonl"
                if path_events.exists():
                    try:
                        lines = path_events.read_text(encoding="utf8").splitlines()
                        for line in lines:
                            if not line:
                                continue
                            try:
                                item = json.loads(line)
                                if not isinstance(item, dict):
                                    raise ValueError("event object required")
                                events.append(item)
                            except ValueError:
                                row["event_capture_errors"].append("INVALID_EVENT_JSON")
                    except (OSError, UnicodeError) as exc:
                        row["event_capture_errors"].append(type(exc).__name__)
            row["events"] = [
                e for e in events if e.get("trace_id") == trace or e.get("case") == case
            ]
            row["evidence_complete"] = (
                row["database_before"] is not None
                and row["database_after"] is not None
                and not row["event_capture_errors"]
            )
            save(
                self.directory / f"request_{self.sequence:03}_{case}.json",
                json.loads(json.dumps(row, default=str)),
            )
        if not row["evidence_complete"]:
            raise RuntimeError("incomplete request evidence; original HTTP result retained")
        if expected is not None:
            assert row["status"] == expected
        return row

    def stop(self):
        outcomes = []
        for row in reversed(self.processes):
            process = row["process"]
            if process.poll() is None:
                try:
                    self.client.post(
                        row["url"] + "/__p4b_owned_stop", headers={"x-p4-control": row["token"]}
                    )
                    process.wait(timeout=12)
                except (httpx.HTTPError, subprocess.TimeoutExpired):
                    process.terminate()  # Exact Popen child only, no process name/port kill.
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            outcomes.append(dict(pid=process.pid, exit_code=process.returncode))
            row["out"].close()
            row["err"].close()
        if hasattr(self, "client"):
            self.client.close()
        save(
            self.directory / "owned_cleanup.json",
            dict(
                processes=outcomes,
                dependency_services="retained; stop separately after evidence review",
            ),
        )


def assert_confirmation_effects(before, after, identifier, action_id, trace_ids):
    assert next(o for o in before["orders"] if o["order_id"] == identifier)["status"] == "paid"
    assert next(o for o in after["orders"] if o["order_id"] == identifier)["status"] == "cancelled"
    audits = [
        a
        for a in after["audit_logs"]
        if a["payload"] == identifier and a["action"] == "cancel_order"
    ]
    assert len(audits) == 1 and audits[0]["trace_id"] in trace_ids
    assert not [a for a in before["audit_logs"] if a["payload"] == identifier]
    keys = [k for k in after["idempotency_keys"] if k["key"] == action_id]
    assert len(keys) == 1 and keys[0]["fingerprint"]
    value = json.loads(keys[0]["response_json"])
    assert value["order_id"] == identifier and value["status"] == "cancelled"
