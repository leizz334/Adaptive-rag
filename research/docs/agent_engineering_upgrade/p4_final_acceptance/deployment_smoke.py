"""Two actual-ASGI starts, health/auth/SSE and clean owned process shutdown."""

import argparse
import json
import signal
import subprocess
import time
from pathlib import Path

import httpx

from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    live_config,
)
from research.docs.agent_engineering_upgrade.p4_final_acceptance.deploy import (
    argv,
    environment,
    private_api_config,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True, choices=["verified_01"])
    args = parser.parse_args()
    manifest, cfg = live_config()
    command(manifest, "ps")
    api = private_api_config(manifest)
    here = Path(__file__).parent
    records = []
    for attempt in range(2):
        started = time.perf_counter()
        with (here / f".private/asgi_{args.instance}_{attempt}.log").open("xb") as log:
            process = subprocess.Popen(argv(api), env=environment(cfg, api), stdout=log, stderr=log)
            record = {"attempt": attempt, "pid": process.pid}
            try:
                with httpx.Client(
                    base_url=f"http://127.0.0.1:{api['port']}", timeout=10, trust_env=False
                ) as client:
                    for _ in range(300):
                        if process.poll() is not None:
                            raise RuntimeError("actual ASGI process exited; inspect private log")
                        try:
                            if client.get("/api/v1/health").status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        time.sleep(0.1)
                    else:
                        raise TimeoutError("ASGI startup")
                    record["process_to_health_ms"] = (time.perf_counter() - started) * 1000
                    ready = client.get("/api/v1/ready").json()
                    caps = client.get("/api/v1/capabilities").json()
                    assert ready["ready"] and all(
                        x["ready"]
                        for x in ready["dependencies"]
                        if x["name"] in {"database", "redis", "vector_store"}
                    )
                    assert client.post("/api/v1/chat", json={"message": "你好"}).status_code == 401
                    response = client.post(
                        "/api/v1/chat/stream",
                        json={"message": "你好"},
                        headers={"authorization": "Bearer " + api["token"]},
                    )
                    events = [
                        json.loads(x[5:])
                        for x in response.text.splitlines()
                        if x.startswith("data:")
                    ]
                    assert (
                        response.status_code == 200
                        and events[-1]["event"] == "done"
                        and any(x["event"] == "answer" for x in events)
                    )
                    record.update(
                        ready=ready,
                        capabilities=caps,
                        unauthorized_status=401,
                        sse_status=200,
                        sse_events=events,
                        secrets_in_public_responses=False,
                    )
                    assert api["token"] not in json.dumps(record) and cfg[
                        "password"
                    ] not in json.dumps(record)
            finally:
                process.terminate()
                process.wait(timeout=15)
                record["exit_code"] = process.returncode
                records.append(record)
                (here / "evidence/e2_deployment_VERIFIED.json").write_text(
                    json.dumps(
                        {
                            "profile": "actual app.asgi; production settings; offline LLM; no neural models",
                            "runs": records,
                            "paid_requests": 0,
                            "active": False,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n"
                )
        shutdown_log = (here / f".private/asgi_{args.instance}_{attempt}.log").read_text()
        assert record["exit_code"] in {0, -signal.SIGTERM}
        assert "Application shutdown complete" in shutdown_log
    print("actual ASGI two starts/real dependencies/auth/SSE PASS")


if __name__ == "__main__":
    main()
