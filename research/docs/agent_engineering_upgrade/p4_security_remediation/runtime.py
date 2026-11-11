"""Owned actual-ASGI private-knowledge runtime; offline providers, no external network."""

import json
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    free_port,
    live_config,
)
from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import (
    TOKENS,
    credential_fixture,
)
from research.docs.agent_engineering_upgrade.p4_final_acceptance.deploy import environment

HERE = Path(__file__).parent


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")


class Runtime:
    def __init__(self, *, mode="private", limit=10000, count=2):
        self.manifest, self.cfg = live_config()
        command(self.manifest, "ps")
        self.directory = HERE / "runs" / ("f_" + uuid.uuid4().hex)
        self.directory.mkdir(parents=True)
        suffix = self.directory.name[2:]
        self.subjects = {"user": "fa_" + suffix, "other": "fb_" + suffix}
        self.mode, self.limit, self.count = mode, limit, count
        self.processes = []
        self.sequence = 0
        self.client = httpx.Client(timeout=15, trust_env=False)

    def start(self):
        for index in range(self.count):
            port = free_port()
            registry = json.loads(credential_fixture())
            for entry in registry["credentials"]:
                if entry["subject"] == "u_demo":
                    entry["subject"] = self.subjects["user"]
                elif entry["subject"] == "u_other":
                    entry["subject"] = self.subjects["other"]
            env = environment(self.cfg, {"credentials": json.dumps(registry)})
            env.update(
                KNOWLEDGE_MODE=self.mode,
                RATE_LIMIT_PER_MINUTE=str(self.limit),
                LOG_LEVEL="WARNING",
                QDRANT_COLLECTION=self.cfg["collection"] + "_f",
            )
            log = (self.directory / f"worker_{index}.log").open("xb")
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "research.docs.agent_engineering_upgrade.p4_final_acceptance.offline",
                    "uvicorn",
                    "app.asgi:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                env=env,
                stdout=log,
                stderr=log,
            )
            row = {"process": process, "log": log, "url": f"http://127.0.0.1:{port}"}
            self.processes.append(row)
            for _ in range(300):
                if process.poll() is not None:
                    raise RuntimeError("owned private ASGI failed; inspect retained log")
                try:
                    if self.client.get(row["url"] + "/api/v1/health").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                raise TimeoutError("private ASGI startup")
        save(
            self.directory / "config.json",
            {
                "mode": self.mode,
                "subjects": self.subjects,
                "rate_limit": self.limit,
                "workers": self.count,
                "database": "postgresql",
                "redis": True,
                "qdrant": True,
                "llm": "OFFLINE_NOT_PAID",
                "embeddings": "CONTROLLED_HASH_NOT_NEURAL",
                "active": False,
                "paid": 0,
            },
        )
        return self

    def request(
        self, method, path, body=None, *, subject="user", worker=0, expected=None, headers=None
    ):
        self.sequence += 1
        supplied = {"authorization": "Bearer " + TOKENS[subject]} if subject else {}
        supplied.update(headers or {})
        response = self.client.request(
            method, self.processes[worker]["url"] + "/api/v1" + path, json=body, headers=supplied
        )
        try:
            data = response.json()
        except ValueError:
            data = response.text
        save(
            self.directory / f"request_{self.sequence:04}.json",
            {
                "method": method,
                "path": path,
                "input": body,
                "subject_fixture": subject,
                "worker": worker,
                "status": response.status_code,
                "body": data,
            },
        )
        if expected is not None:
            assert response.status_code == expected, (response.status_code, data)
        return response

    def stop(self):
        outcomes = []
        for row in self.processes:
            process = row["process"]
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
            outcomes.append({"pid": process.pid, "exit_code": process.returncode})
            row["log"].close()
        self.client.close()
        save(
            self.directory / "owned_cleanup.json",
            {
                "processes": outcomes,
                "expected_exits": [0, -signal.SIGTERM],
                "services_retained": True,
            },
        )
        assert all(x["exit_code"] in [0, -signal.SIGTERM] for x in outcomes)
