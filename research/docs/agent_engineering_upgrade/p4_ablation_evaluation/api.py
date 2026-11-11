"""Single owned API child. All arm requests are serialized by the phase runner."""

import json
import os
import secrets
import subprocess
import sys
import time
import uuid

import httpx

from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import free_port
from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import TOKENS
from research.docs.agent_engineering_upgrade.p4_real_llm_e2e.run import normalized

from .common import ROOT, RUN
from .meter import SafetyStop, write


class Api:
    def __init__(self, label, cfg):
        self.label, self.cfg = label, cfg
        instance = len(list(RUN.glob("worker_" + label + "*"))) + 1
        self.tag = label + f"_{instance:02d}"
        self.directory = RUN / ("worker_" + self.tag)
        if self.directory.exists():
            raise SafetyStop(
                "stage worker already exists; inspect durable state, no automatic paid replay"
            )
        self.port, self.token = free_port(), secrets.token_hex(24)
        self.url = f"http://127.0.0.1:{self.port}"
        self.out = (RUN / (self.tag + "_stdout.log")).open("wb")
        self.err = (RUN / (self.tag + "_stderr.log")).open("wb")
        env = os.environ.copy()
        for name in list(env):
            if name.lower().endswith("_proxy"):
                env.pop(name)
        env.update(
            P4D_CONTROL_TOKEN=self.token,
            LANGCHAIN_TRACING_V2="false",
            LANGSMITH_TRACING="false",
            EXPERIENCE_MEMORY_MODE="off",
        )
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-B",
                "-m",
                __package__ + ".worker",
                "--port",
                str(self.port),
                "--stage",
                label,
                "--instance",
                str(instance),
            ],
            cwd=ROOT,
            env=env,
            stdout=self.out,
            stderr=self.err,
        )
        self.client = httpx.Client(timeout=180, trust_env=False)

    def wait(self):
        for _ in range(1800):
            if self.process.poll() is not None:
                raise RuntimeError("worker startup failed;inspect private local logs")
            try:
                if (
                    self.client.get(self.url + "/api/v1/health").status_code == 200
                    and (self.directory / "startup.json").exists()
                ):
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.1)
        raise TimeoutError("startup bounded180s")

    def stop(self):
        if self.process.poll() is None:
            try:
                self.client.post(self.url + "/__p4d_stop", headers={"x-p4-control": self.token})
                self.process.wait(timeout=15)
            except (httpx.HTTPError, subprocess.TimeoutExpired):
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        write(
            RUN / (self.tag + "_owned_cleanup.json"),
            dict(pid=self.process.pid, exit_code=self.process.returncode),
        )
        self.client.close()
        self.out.close()
        self.err.close()

    def request(self, case, payload, protocol="json", *, arm="BASE", identity="user"):
        trace = "p4c_" + uuid.uuid4().hex
        row = dict(
            case=case,
            before=normalized(self.cfg),
            payload=payload,
            trace_id=trace,
            tools=[],
            events=[],
        )
        started = time.perf_counter()
        try:
            r = self.client.post(
                self.url + "/api/v1/chat" + ("/stream" if protocol == "sse" else ""),
                json=payload,
                headers={
                    "authorization": "Bearer " + TOKENS[identity] if identity else "",
                    "x-p4-case": case,
                    "x-trace-id": trace,
                    "x-p4-arm": arm,
                    "x-p4-control": self.token,
                },
            )
            row.update(status=r.status_code, text=r.text)
            if protocol == "sse":
                events = [
                    json.loads(line[5:]) for line in r.text.splitlines() if line.startswith("data:")
                ]
                answers = [e["data"] for e in events if e["event"] == "answer"]
                row["body"] = answers[-1] if answers else {}
                row["protocol_valid"] = bool(
                    events
                    and events[0]["event"] == "started"
                    and events[-1]["event"] == "done"
                    and len(answers) == 1
                    and not any(e["event"] == "error" for e in events)
                    and "".join(e.get("text", "") for e in events if e["event"] == "token")
                    == row["body"].get("answer")
                )
            else:
                row["body"] = r.json()
                row["protocol_valid"] = True
        except BaseException as exc:
            row.update(
                transport_error=type(exc).__name__, status=None, protocol_valid=False, body={}
            )
        finally:
            row.update(
                latency_ms=(time.perf_counter() - started) * 1000, after=normalized(self.cfg)
            )
            path = self.directory / "events.jsonl"
            if path.exists():
                row["events"] = [
                    e
                    for e in [json.loads(line) for line in path.read_text().splitlines()]
                    if e.get("trace_id") == trace
                ]
                # Trace batches use the root trace_id through captured tools; spans are kept raw below.
                all_events = [json.loads(line) for line in path.read_text().splitlines()]
                row["spans"] = [
                    s for e in all_events if e.get("case") == case for s in e.get("spans", [])
                ]
                row["tools"] = [t for e in row["events"] for t in e.get("calls", [])]
            write(RUN / ("request_" + trace + ".json"), row)
        return row
