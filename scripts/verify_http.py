"""Verify the archived FastAPI startup and actual HTTP/SSE on a disposable PostgreSQL."""

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import asyncpg
import httpx
from verify_postgres import SANDBOX, source_env


async def check_database(port):
    connection = await asyncpg.connect(
        host="127.0.0.1",
        port=port,
        database=SANDBOX,
        user="adaptive_rag_final",
        timeout=4,
    )
    try:
        if await connection.fetchval("show cluster_name") != SANDBOX:
            raise RuntimeError("HTTP check requires the disposable PostgreSQL instance")
    finally:
        await connection.close()


def verify(source, database_port):
    if (source / ".env").exists() or (source / ".git").exists():
        raise RuntimeError("Use a Git source archive without environment files")
    asyncio.run(check_database(database_port))
    env = source_env(database_port)
    env.update(
        APP_ENV="testing",
        DATABASE_URL=env["ADAPTIVE_RAG_FINAL_PG_URL"],
        LOCAL_EMBEDDING_ENABLED="false",
        CROSS_ENCODER_ENABLED="false",
        UNSTRUCTURED_ENABLED="false",
        REDIS_URL="",
        QDRANT_URL="",
        DEEPSEEK_API_KEY="",
    )
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        port = server.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.asgi:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=source,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}/api/v1", timeout=8, trust_env=False
        ) as client:
            deadline = time.monotonic() + 20
            while True:
                try:
                    health = client.get("/health")
                    health.raise_for_status()
                    break
                except httpx.ConnectError:
                    if process.poll() is not None or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.2)
            ready = client.get("/ready")
            ready.raise_for_status()
            status = ready.json()
            assert status["ready"] and any(
                dep["name"] == "database" and dep["ready"] for dep in status["dependencies"]
            )
            capabilities = client.get("/capabilities")
            capabilities.raise_for_status()
            assert capabilities.json()["database"] == "postgresql"
            payload = {"user_id": "u_http_smoke", "message": "你好"}
            with client.stream("POST", "/chat/stream", json=payload) as stream:
                stream.raise_for_status()
                assert stream.headers["content-type"].startswith("text/event-stream")
                events = [
                    json.loads(line.removeprefix("data: "))
                    for line in stream.iter_lines()
                    if line.startswith("data: ")
                ]
            types = [event["event"] for event in events]
            assert types[0] == "started" and types[-1] == "done"
            answer = next(event["data"] for event in events if event["event"] == "answer")
            assert answer["answer"] and answer["trace_id"] and not answer["refused"]
            return {
                "health": health.status_code,
                "readiness": status,
                "capabilities": capabilities.json(),
                "sse_events": types,
                "answer_and_trace_present": True,
                "server": "uvicorn-loopback",
            }
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True, help="disposable PostgreSQL port")
    arguments = parser.parse_args()
    print(
        json.dumps(verify(arguments.source.resolve(), arguments.port), ensure_ascii=True, indent=2)
    )
