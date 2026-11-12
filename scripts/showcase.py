"""Guarded zero-paid Ubuntu showcase launcher; run from the repository root.

init creates a new owned run; serve stays foreground; stop retains all volumes.
No production credentials, external model requests or arbitrary Docker targets.
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "research/docs/agent_engineering_upgrade"
PRIVATE = STATE / "s1_showcase_release/.private"


def run_paths(run_id):
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,23}", run_id):
        raise ValueError("invalid isolated run id")
    # Docker project syntax is deliberately narrower than local directory syntax.
    if "-" in run_id:
        raise ValueError("run id must use lowercase letters, digits and underscores")
    directory = PRIVATE / run_id
    if directory.is_symlink():
        raise ValueError("symlink run target forbidden")
    project = "p4b_showcase_" + run_id
    manifest = STATE / f"p4_dependency_integration/.private/{project}/manifest.json"
    return directory, project, manifest


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def read_run(run_id):
    directory, project, manifest = run_paths(run_id)
    row = json.loads((directory / "run.json").read_text())
    expected = dict(version=1, run_id=run_id, project=project, manifest=str(manifest))
    if row != expected:
        raise ValueError("saved run target mismatch")
    from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import load

    cfg = load(manifest)
    if cfg["project"] != project:
        raise ValueError("manifest target mismatch")
    return directory, manifest, cfg


def bind_demo(run_id):
    directory, manifest, cfg = read_run(run_id)
    os.environ["P4B_RUN_LIVE"] = "1"
    os.environ["P4B_MANIFEST"] = str(manifest)
    from research.docs.agent_engineering_upgrade.s1_web_upgrade import demo

    demo.PRIVATE = directory
    demo.API = directory / "demo_api.json"
    return directory, manifest, cfg, demo


def public_info(run_id):
    directory, project, _ = run_paths(run_id)
    row = json.loads((directory / "demo_api.json").read_text())
    return dict(
        run_id=run_id,
        project=project,
        url=f"http://127.0.0.1:{row['port']}",
        private_credentials_file=str(directory / "demo_api.json"),
        llm="CONTROLLED_OFFLINE_NOT_REAL_LLM",
        paid_requests=0,
        experience_active=False,
    )


def initialize(run_id):
    directory, project, manifest = run_paths(run_id)
    if directory.exists():
        raise FileExistsError("run already exists; use start/status/serve, never reinitialize")
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise RuntimeError(
            "build frontend first: npm ci --prefix frontend && npm run build --prefix frontend"
        )
    directory.mkdir(parents=True, mode=0o700)
    save_new(
        directory / "run.json",
        dict(version=1, run_id=run_id, project=project, manifest=str(manifest)),
    )
    from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
        command,
        prepare,
    )

    actual = prepare(manifest.parent.parent, project)
    if actual != manifest:
        raise ValueError("prepared manifest target mismatch")
    os.environ["P4B_RUN_LIVE"] = "1"
    os.environ["P4B_MANIFEST"] = str(manifest)
    command(manifest, "up")
    # Initial empty owned DB only; never run the destructive roundtrip on resume.
    log = directory / "initial_migration.private.log"
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "research.docs.agent_engineering_upgrade.p4_dependency_integration.migrate",
                "--roundtrip",
            ],
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=stream,
            stderr=stream,
            check=True,
        )
    _, _, _, demo = bind_demo(run_id)
    demo.prepare()
    save_new(directory / "initialized.json", dict(ready=True, project=project, paid_requests=0))


def process_facts(pid):
    try:
        path = Path("/proc") / str(int(pid))
        fields = (path / "stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return dict(
            start_ticks=fields[19],
            uid=path.stat().st_uid,
            cwd=str((path / "cwd").resolve()),
            cmdline=[a.decode() for a in (path / "cmdline").read_bytes().split(b"\0") if a],
        )
    except (OSError, ValueError, IndexError):
        return None


def matching_process(record, facts):
    if (
        not facts
        or record.get("start_ticks") != facts.get("start_ticks")
        or facts.get("uid") != os.getuid()
        or facts.get("cwd") != str(ROOT)
    ):
        return False
    args = facts.get("cmdline", [])
    return (
        ["-m", "scripts.showcase"] in [args[i : i + 2] for i in range(len(args))]
        and "serve" in args
        and ["--run-id", record.get("run_id")] in [args[i : i + 2] for i in range(len(args))]
    )


def current_process(directory):
    path = directory / "current_process.json"
    return json.loads(path.read_text()) if path.exists() else None


def clear_proxy_environment():
    """Only this child process is changed; localhost demo never uses ambient proxies."""
    for key in list(os.environ):
        if key.lower().endswith("_proxy"):
            os.environ.pop(key)


def serve(run_id):
    clear_proxy_environment()
    directory, _, _, demo = bind_demo(run_id)
    old = current_process(directory)
    if old and matching_process(old, process_facts(old["pid"])):
        raise RuntimeError("owned API is already running")
    facts = process_facts(os.getpid())
    record = dict(run_id=run_id, pid=os.getpid(), start_ticks=facts["start_ticks"])
    save_new(directory / f"api_process_{uuid4().hex}.json", record)
    # A runtime pointer is mutable; immutable process records above preserve each start.
    pointer = directory / "current_process.json"
    fd = os.open(pointer, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(record, stream)
    demo.serve()


def control(run_id, action):
    directory, manifest, _, _ = bind_demo(run_id)
    from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import command

    if action == "stop":
        record = current_process(directory)
        if record:
            facts = process_facts(record["pid"])
            if facts is not None:
                if record.get("run_id") != run_id or not matching_process(record, facts):
                    raise ValueError("stale/foreign process; no stop authorized")
                os.kill(record["pid"], signal.SIGTERM)
                deadline = time.monotonic() + 15
                while process_facts(record["pid"]) is not None and time.monotonic() < deadline:
                    time.sleep(0.1)
                if process_facts(record["pid"]) is not None:
                    raise TimeoutError("owned API did not stop; dependencies preserved")
    command(manifest, action)
    return dict(run_id=run_id, action=action, volumes_retained=True)


def status(run_id):
    _, _, _, _ = bind_demo(run_id)
    import httpx

    info = public_info(run_id)
    api = json.loads(Path(info["private_credentials_file"]).read_text())
    result = dict(run_id=run_id, url=info["url"], paid_requests=0, experience_active=False)
    with httpx.Client(timeout=10, trust_env=False) as client:
        result["health"] = client.get(info["url"] + "/api/v1/health").status_code
        ready = client.get(info["url"] + "/api/v1/ready")
        result["readiness"] = ready.json()
        capability = client.get(info["url"] + "/api/v1/capabilities").json()
        result["capabilities"] = capability
        identity = client.get(
            info["url"] + "/api/v1/auth/me",
            headers={"authorization": "Bearer " + api["tokens"]["a"]},
        )
        result["authenticated_identity_verified"] = (
            identity.status_code == 200 and identity.json().get("subject") == "web_demo_a"
        )
    actual = {r["name"]: r["ready"] for r in result["readiness"]["dependencies"]}
    if (
        result["health"] != 200
        or not result["authenticated_identity_verified"]
        or not all(actual.get(k) for k in ["database", "redis", "vector_store"])
        or capability["database"] != "postgresql"
        or capability["cache"] != "redis"
        or capability["vector_store"] != "PrivateVectorStore"
        or capability["llm"] != "offline"
    ):
        raise RuntimeError("showcase dependencies/identity/profile not verified")
    return result


def browser(run_id, cancel_order):
    """Real Chromium against an already healthy owned API; never expose auth captures."""
    if cancel_order not in {"ORD95102", "ORD95103", "ORD95105", "ORD95106", "ORD95107"}:
        raise ValueError("choose an unused synthetic cancellation order")
    status(run_id)
    directory, _, _, _ = bind_demo(run_id)
    browser_id = "showcase_" + uuid4().hex
    output = directory / "browser_runs"
    output.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(
        S1WEB_DEMO_CONFIG=str(directory / "demo_api.json"),
        S1WEB_OUTPUT_ROOT=str(output),
        S1WEB_BROWSER_RUN=browser_id,
        S1WEB_CANCEL_ORDER=cancel_order,
    )
    log = output / (browser_id + ".private.log")
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        result = subprocess.run(
            ["npm", "run", "test:e2e"], cwd=ROOT / "frontend", env=env, stdout=stream, stderr=stream
        )
    report = json.loads((output / ("browser-" + browser_id + ".json")).read_text())
    cases = []
    for suite in report["suites"]:
        for spec in suite.get("specs", []):
            for item in spec["tests"]:
                row = item["results"][0]
                cases.append(
                    dict(title=spec["title"], status=row["status"], duration_ms=row["duration"])
                )
    summary = dict(
        run_id=run_id,
        browser_run_id=browser_id,
        engine="REAL_PLAYWRIGHT_CHROMIUM",
        cases=cases,
        passed=sum(x["status"] == "passed" for x in cases),
        failed=sum(x["status"] != "passed" for x in cases),
        retries=0,
        API_mock_routes=False,
        real_dependencies=["FastAPI", "PostgreSQL", "Redis", "Qdrant"],
        model="CONTROLLED_OFFLINE_NOT_REAL_LLM",
        paid_requests=0,
        cancellation_order=cancel_order,
        private_raw_report=str(output / ("browser-" + browser_id + ".json")),
    )
    save_new(output / (browser_id + ".summary.json"), summary)
    if result.returncode or summary["failed"] or len(cases) < 6:
        raise RuntimeError("real browser validation failed; private raw evidence retained")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["init", "start", "serve", "status", "stop", "info", "browser"]
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--cancel-order",
        default="ORD95102",
        help="browser only: unused synthetic cancellation order",
    )
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.action == "init":
        initialize(args.run_id)
    elif args.action == "serve":
        serve(args.run_id)
    elif args.action == "browser":
        print(json.dumps(browser(args.run_id, args.cancel_order), ensure_ascii=False, indent=2))
    else:
        result = (
            status(args.run_id)
            if args.action == "status"
            else public_info(args.run_id)
            if args.action == "info"
            else control(args.run_id, args.action)
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # No credential-bearing DSN/registry or arbitrary exception text to console.
        print(
            f"SHOWCASE_FAILED={type(exc).__name__}; inspect owned private state and RECOVERY.md",
            file=sys.stderr,
        )
        sys.exit(1)
