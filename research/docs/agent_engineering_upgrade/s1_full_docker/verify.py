"""Explicit-target real Docker acceptance. Never removes volumes or prints credentials.

Run with --project, --source, --port and a NEW --output directory. This runner
mutates only the verified s1-docker-v1 project, runs seven existing browser tests,
and preserves the separate synthetic persistence document for later inspection.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import traceback
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[4]
LABEL = "io.adaptive-rag.showcase"
SERVICES = {"api", "bootstrap", "initialize", "postgres", "redis", "qdrant"}


def save_new(path, value, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


class Acceptance:
    def __init__(self, args):
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", args.project):
            raise ValueError("invalid project")
        if not 1024 <= args.port <= 65535:
            raise ValueError("invalid loopback port")
        self.project, self.port = args.project, args.port
        self.source = args.source.resolve(strict=True)
        self.compose_file = self.source / "compose.showcase.yml"
        if not self.compose_file.is_file() or self.compose_file.is_symlink():
            raise ValueError("missing explicit source compose")
        self.output = args.output.absolute()
        self.output.mkdir(parents=True, mode=0o700, exist_ok=False)
        self.private = self.output / ".private"
        self.private.mkdir(mode=0o700)
        self.browser_root = args.browser_root.resolve(strict=True)
        self.env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
        self.env["SHOWCASE_PORT"] = str(self.port)
        self.compose = ["docker", "compose", "-p", self.project, "-f", str(self.compose_file)]
        self.stage = "setup"
        self.steps = []
        self.tokens = None

    def run(self, argv, **kwargs):
        try:
            result = subprocess.run(
                argv,
                cwd=self.source,
                env=self.env,
                capture_output=True,
                text=True,
                timeout=kwargs.pop("timeout", 120),
                **kwargs,
            )
        except subprocess.TimeoutExpired as exc:
            save_new(
                self.private / ("subprocess-" + uuid4().hex + ".json"),
                dict(
                    stage=self.stage,
                    argv=argv,
                    timeout=True,
                    stdout=str(exc.stdout or ""),
                    stderr=str(exc.stderr or ""),
                ),
            )
            raise
        if result.returncode:
            save_new(
                self.private / ("subprocess-" + uuid4().hex + ".json"),
                dict(
                    stage=self.stage,
                    argv=argv,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                ),
            )
            raise RuntimeError("subprocess failed")
        return result.stdout

    def guard(self):
        ids = self.run(
            ["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={self.project}"]
        ).split()
        if not ids:
            raise ValueError("target project absent")
        containers = json.loads(self.run(["docker", "inspect", *ids]))
        seen = set()
        for container in containers:
            labels = container["Config"]["Labels"]
            service = labels.get("com.docker.compose.service")
            if (
                labels.get(LABEL) != "s1-docker-v1"
                or service not in SERVICES
                or labels.get("com.docker.compose.project") != self.project
                or Path(labels.get("com.docker.compose.project.working_dir", "")).resolve()
                != self.source
                or labels.get("com.docker.compose.project.config_files") != str(self.compose_file)
            ):
                raise ValueError("target ownership/source mismatch")
            seen.add(service)
            if service == "api":
                ports = container["HostConfig"]["PortBindings"].get("8000/tcp", [])
                if ports != [{"HostIp": "127.0.0.1", "HostPort": str(self.port)}]:
                    raise ValueError("target port mismatch")
        if seen != SERVICES:
            raise ValueError("incomplete target project")

    def mutate(self, *arguments):
        self.guard()  # Recheck ownership immediately before EVERY lifecycle mutation.
        self.run(self.compose + list(arguments), timeout=240)

    def credentials(self):
        raw = self.run(
            self.compose
            + ["exec", "-T", "api", "cat", "/var/lib/showcase/development_credentials.json"]
        )
        row = json.loads(raw)
        if set(row["tokens"]) != {"a", "b"}:
            raise ValueError("unexpected credentials")
        return row, hashlib.sha256(raw.encode()).hexdigest()

    def request(self, method, path, *, subject="a", **kwargs):
        with httpx.Client(
            base_url=f"http://127.0.0.1:{self.port}", timeout=15, trust_env=False
        ) as client:
            return client.request(
                method,
                "/api/v1" + path,
                headers={"Authorization": "Bearer " + self.tokens[subject]},
                **kwargs,
            )

    def ready(self):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                self.run(
                    self.compose
                    + ["exec", "-T", "api", "python", "-m", "app.demo.docker", "health"],
                    timeout=8,
                )
                return
            except (RuntimeError, subprocess.TimeoutExpired):
                time.sleep(2)
        raise RuntimeError("readiness timeout")

    def sql(self, query):
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
        tables = self.sql(
            "SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='public'"
        )
        if not tables or any(not re.fullmatch(r"[a-z_]+", t) for t in tables):
            raise ValueError("unexpected schema")
        counts = {table: self.sql(f'SELECT to_json(count(*)) FROM "{table}"') for table in tables}
        orders = self.sql(
            "SELECT json_agg(x ORDER BY order_id) FROM (SELECT order_id,user_id,status,total_cents FROM orders WHERE order_id LIKE 'ORD95%') x"
        )
        audit = self.sql(
            "SELECT coalesce(json_agg(x ORDER BY action),'[]'::json) FROM (SELECT action,count(*) AS count FROM audit_logs GROUP BY action) x"
        )
        return dict(
            schema=self.sql(
                "SELECT json_agg(version_num ORDER BY version_num) FROM alembic_version"
            ),
            tables=tables,
            counts=counts,
            orders=orders,
            audit_actions=audit,
        )

    def knowledge_check(self, document, query):
        own = self.request("GET", "/knowledge/documents")
        foreign = self.request("GET", "/knowledge/documents", subject="b")
        if own.status_code != 200 or foreign.status_code != 200:
            raise AssertionError("knowledge list unavailable")
        if document not in {d["document_id"] for d in own.json()["documents"]}:
            raise AssertionError("persistent document missing")
        if document in {d["document_id"] for d in foreign.json()["documents"]}:
            raise AssertionError("foreign document exposed")
        for subject in ("a", "b"):
            response = self.request(
                "POST", "/knowledge/search", subject=subject, json=dict(query=query, mode="hybrid")
            )
            if response.status_code != 200:
                raise AssertionError("knowledge search unavailable")
            present = document in {c["document_id"] for c in response.json()["chunks"]}
            if present != (subject == "a"):
                raise AssertionError("knowledge persistence/owner isolation failure")
        denied = self.request("DELETE", "/knowledge/documents/" + document, subject="b")
        if denied.status_code != 404:
            raise AssertionError("foreign deletion not denied")

    def history_check(self, session_id):
        own = self.request("GET", f"/sessions/{session_id}/messages")
        foreign = self.request("GET", f"/sessions/{session_id}/messages", subject="b")
        missing = self.request(
            "GET", "/sessions/nonexistent-docker-acceptance/messages", subject="b"
        )
        if own.status_code != 200 or not own.json().get("messages"):
            raise AssertionError("durable SQL history missing")
        if (
            foreign.status_code != 404
            or missing.status_code != 404
            or foreign.json() != missing.json()
        ):
            raise AssertionError("history owner isolation failed")
        return hashlib.sha256(own.content).hexdigest()

    def browser(self, cancel_order):
        env = dict(
            self.env,
            S1WEB_DEMO_CONFIG=str(self.private / "browser-config.json"),
            S1WEB_OUTPUT_ROOT=str(self.private),
            S1WEB_BROWSER_RUN="acceptance",
            S1WEB_CANCEL_ORDER=cancel_order,
        )
        result = subprocess.run(
            ["npx", "playwright", "test"],
            cwd=self.browser_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        fd = os.open(self.private / "browser.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(result.stdout + result.stderr)
        report = json.loads((self.private / "browser-acceptance.json").read_text())
        stats = report["stats"]
        save_new(
            self.output / "browser_stats.json",
            {k: stats.get(k, 0) for k in ("expected", "unexpected", "flaky", "skipped")},
            0o644,
        )
        save_new(self.output / "after_browser_database.json", self.snapshot(), 0o644)
        if (
            result.returncode
            or stats["expected"] != 7
            or any(stats.get(k, 0) for k in ("unexpected", "flaky", "skipped"))
        ):
            raise AssertionError("seven real browser scenarios did not pass")
        return {k: stats[k] for k in ("expected", "unexpected", "flaky", "skipped")}

    def execute(self):
        self.stage = "initial_guard_and_readiness"
        self.guard()
        self.ready()
        credentials, credential_hash = self.credentials()
        self.tokens = credentials["tokens"]
        save_new(self.private / "development_credentials.json", credentials)
        save_new(self.private / "browser-config.json", dict(port=self.port, tokens=self.tokens))
        initial = self.snapshot()
        save_new(self.output / "initial_database.json", initial, 0o644)
        cancel = next(
            (
                r["order_id"]
                for r in initial["orders"]
                if r["status"] == "paid"
                and r["order_id"] in {"ORD95102", "ORD95103", "ORD95105", "ORD95106", "ORD95107"}
            ),
            None,
        )
        if cancel is None:
            raise ValueError("no unused browser cancellation fixture")
        self.stage = "browser"
        stats = self.browser(cancel)
        self.stage = "persistence_baseline"
        document = "docker-persistence-" + uuid4().hex[:20]
        query = "鲸蓝持久凭证" + uuid4().hex
        response = self.request(
            "POST",
            "/knowledge/documents/" + document,
            json=dict(title=query, content=f"# {query}\n{query}：容器重启后保留的合成私有知识。"),
        )
        if response.status_code != 200:
            raise AssertionError("persistence document creation failed")
        self.knowledge_check(document, query)
        sessions = self.sql(
            "SELECT coalesce(json_agg(session_id), '[]'::json) FROM sessions WHERE user_id='web_demo_a'"
        )
        if not sessions:
            raise AssertionError("browser did not persist SQL sessions")
        history_session = sessions[0]
        history_hash = self.history_check(history_session)
        baseline = self.snapshot()
        save_new(self.output / "baseline_database.json", baseline, 0o644)
        if next(r for r in baseline["orders"] if r["order_id"] == cancel)["status"] != "cancelled":
            raise AssertionError("browser cancellation not persisted")
        if baseline["counts"]["audit_logs"] <= initial["counts"]["audit_logs"]:
            raise AssertionError("no actual browser audit writes")
        self.steps.append(dict(stage="browser", scenarios=stats, database=baseline))
        for stage, operations in [
            ("api_restart", [("restart", "api")]),
            (
                "dependencies_restart",
                [("restart", "postgres", "redis", "qdrant"), ("restart", "api")],
            ),
            ("stop_start_up", [("stop",), ("start",), ("up", "-d")]),
        ]:
            self.stage = stage
            for operation in operations:
                self.mutate(*operation)
            self.ready()
            save_new(self.output / (stage + "_database.json"), self.snapshot(), 0o644)
            _, actual_hash = self.credentials()
            if actual_hash != credential_hash:
                raise AssertionError("credentials rotated")
            self.knowledge_check(document, query)
            if self.history_check(history_session) != history_hash:
                raise AssertionError("durable history changed across lifecycle")
            snapshot = self.snapshot()
            if snapshot != baseline:
                raise AssertionError("persistent SQL state changed during lifecycle operations")
            self.steps.append(
                dict(
                    stage=stage,
                    credentials_unchanged=True,
                    knowledge_owner_isolated=True,
                    history_owner_isolated=True,
                    sql_unchanged=True,
                    database=snapshot,
                )
            )
            save_new(self.output / (stage + ".json"), self.steps[-1], 0o644)
        save_new(
            self.output / "acceptance.json",
            dict(
                version=1,
                project=self.project,
                source=str(self.source),
                port=self.port,
                credential_sha256=credential_hash,
                initial_database=initial,
                persistence_document=document,
                steps=self.steps,
                paid_requests=0,
                llm="CONTROLLED_OFFLINE_NOT_REAL_LLM",
                windows="NOT_RUN",
            ),
            0o644,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--browser-root", type=Path, default=ROOT / "frontend")
    args = parser.parse_args()
    os.umask(0o077)
    runner = None
    try:
        runner = Acceptance.__new__(Acceptance)
        runner.__init__(args)
        runner.execute()
    except Exception as exc:
        # Only use directories successfully created for this invocation; never
        # overwrite diagnostics belonging to an older run with the same output.
        if runner is not None and hasattr(runner, "private") and runner.private.is_dir():
            fd = os.open(
                runner.private / "failure.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(fd, "w") as stream:
                stream.write(traceback.format_exc())
                stream.flush()
                os.fsync(stream.fileno())
            save_new(
                runner.output / "failure.json",
                dict(exception_type=type(exc).__name__, stage=getattr(runner, "stage", "setup")),
                0o644,
            )
        print(type(exc).__name__)
        raise SystemExit(1) from None
    print("Acceptance PASS; sanitized evidence saved")


if __name__ == "__main__":
    main()
