"""Owned Uvicorn child and real HTTP evidence. No ASGI/TestClient transport."""

import argparse
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import time

import httpx

from research.docs.agent_engineering_upgrade.p4_api_e2e.manage import HERE, ROOT, git, save, sha


class HttpRun:
    def __init__(self, name):
        if not name or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
            for c in name
        ):
            raise ValueError("Bounded run id required")
        self.directory = HERE / "runs" / name
        self.directory.mkdir(parents=True, exist_ok=False)
        self.process = None
        self.client = None
        self.token = secrets.token_hex(24)
        self.sequence = 0

    def start(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        env = {
            k: v
            for k, v in os.environ.items()
            if k.upper()
            in {
                "PATH",
                "SYSTEMROOT",
                "WINDIR",
                "TEMP",
                "TMP",
                "PATHEXT",
                "COMSPEC",
                "USERPROFILE",
                "CONDA_PREFIX",
            }
        }
        env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", P4_CONTROL_TOKEN=self.token)
        self.stdout = (self.directory / "stdout.log").open("wb")
        self.stderr = (self.directory / "stderr.log").open("wb")
        cmd = [
            sys.executable,
            "-B",
            "-m",
            "research.docs.agent_engineering_upgrade.p4_api_e2e.worker",
            "--run-dir",
            str(self.directory),
            "--port",
            str(port),
        ]
        self.process = subprocess.Popen(
            cmd,
            cwd=ROOT,
            env=env,
            stdout=self.stdout,
            stderr=self.stderr,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        save(
            self.directory / "process.json",
            dict(
                pid=self.process.pid,
                command=cmd,
                url=self.url,
                python=sys.executable,
                head=git("rev-parse", "HEAD"),
                worker_sha256=sha(HERE / "worker.py"),
                paid_api=False,
                transport="real_TCP_HTTPX_to_Uvicorn_process",
                new_worktree_created=False,
            ),
        )
        self.client = httpx.Client(base_url=self.url, timeout=12, trust_env=False)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError("Owned worker startup failed; inspect retained stderr.log")
            try:
                response = self.client.get("/api/v1/health", headers={"x-p4-case": "startup"})
                if response.status_code == 200 and (self.directory / "startup.json").exists():
                    return self
            except httpx.TransportError:
                pass
            time.sleep(0.05)
        raise TimeoutError("Owned Uvicorn health startup deadline")

    def snapshot(self):
        database = self.directory / "app.sqlite3"
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            names = [
                r[0]
                for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            return {
                name: [
                    dict(row)
                    for row in connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid')
                ]
                for name in names
            }

    def events(self, case):
        path = self.directory / "events.jsonl"
        return [
            row
            for line in path.read_text(encoding="utf8").splitlines()
            if line.strip() and (row := json.loads(line)).get("case") == case
        ]

    def wait_events(self, case, kind, timeout=2):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            rows = self.events(case)
            if any(row["kind"] == kind for row in rows):
                return rows
            time.sleep(0.02)
        return self.events(case)

    def request(
        self,
        case,
        method,
        path,
        payload=None,
        *,
        fault="none",
        headers=None,
        stream=False,
        disconnect=False,
    ):
        self.sequence += 1
        before = self.snapshot()
        supplied = {"x-p4-case": case, "x-p4-fault": fault, "x-trace-id": f"p4-{case}"}
        supplied.update(headers or {})
        started = time.perf_counter()
        data, status, result_headers, stream_items, transport_error = None, None, {}, [], None
        try:
            if stream:
                with self.client.stream(method, path, json=payload, headers=supplied) as response:
                    status, result_headers = response.status_code, dict(response.headers)
                    for line in response.iter_lines():
                        if line.startswith("data:"):
                            item = json.loads(line[5:].strip())
                            stream_items.append(item)
                            if disconnect and item.get("event") == "started":
                                # Ensure the graph/model began, then close the actual socket.
                                self.wait_events(case, "model_started")
                                break
                if disconnect:
                    self.wait_events(case, "stream_closed")
                data = stream_items
            else:
                response = self.client.request(method, path, json=payload, headers=supplied)
                status, result_headers = response.status_code, dict(response.headers)
                try:
                    data = response.json()
                except ValueError:
                    data = dict(non_json_body=response.text[:800])
        except httpx.HTTPError as exc:
            transport_error = type(exc).__name__
            data = stream_items if stream else None
        if path.startswith("/api/v1/chat"):
            self.wait_events(case, "tools")
        record = dict(
            case=case,
            method=method,
            url=self.url + path,
            request=payload,
            fault=fault,
            status=status,
            response_headers=result_headers,
            body=data,
            transport_error=transport_error,
            latency_ms=(time.perf_counter() - started) * 1000,
            database_before=before,
            database_after=self.snapshot(),
            events=self.events(case),
            deliberate_disconnect=disconnect,
        )
        save(self.directory / f"request_{self.sequence:03d}_{case}.json", record)
        return record

    def stop(self):
        stopped_gracefully = False
        try:
            if self.process is not None and self.process.poll() is None:
                if self.client:
                    try:
                        response = self.client.post(
                            "/__p4/stop",
                            headers={"x-p4-owner": self.token, "x-p4-case": "shutdown"},
                        )
                        stopped_gracefully = response.status_code == 200
                    except httpx.HTTPError:
                        pass
                try:
                    self.process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self.process.terminate()  # Only this Popen handle, never enumerate other Python processes.
                    self.process.wait(timeout=5)
            if self.process:
                save(
                    self.directory / "owned_cleanup.json",
                    dict(
                        pid=self.process.pid,
                        exit_code=self.process.poll(),
                        graceful_request=stopped_gracefully,
                        stopped_only_owned_process=True,
                    ),
                )
        finally:
            if self.client:
                self.client.close()
            for name in ("stdout", "stderr"):
                if hasattr(self, name):
                    getattr(self, name).close()


def probe(name):
    run = HttpRun(name)
    try:
        run.start()
        rows = [
            run.request(route, "GET", "/api/v1/" + route)
            for route in ("health", "ready", "capabilities")
        ]
        rows.append(
            run.request(
                "startup_greeting", "POST", "/api/v1/chat", dict(message="你好", user_id="u_demo")
            )
        )
        manifest = json.loads((run.directory / "startup.json").read_bytes())
        assert all(row["status"] == 200 for row in rows)
        assert manifest["pid"] == run.process.pid and manifest["provider"] == "ControlledLLM"
        assert manifest["actual_engine_url"].startswith("sqlite+aiosqlite:///")
        assert len(run.snapshot()["orders"]) >= 3
        assert any(e["kind"] == "spans" for e in rows[-1]["events"])
        save(
            run.directory / "validation.json",
            dict(
                startup=True,
                real_http_requests=4,
                provider=manifest["provider"],
                isolated_sqlite=True,
                synthetic_seed=True,
                local_trace=True,
                paid_model_calls=0,
            ),
        )
        print(
            json.dumps(
                dict(
                    status="PASS_STARTUP",
                    provider=manifest["provider"],
                    url=run.url,
                    pid=run.process.pid,
                )
            )
        )
    finally:
        run.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", required=True)
    probe(parser.parse_args().probe)
