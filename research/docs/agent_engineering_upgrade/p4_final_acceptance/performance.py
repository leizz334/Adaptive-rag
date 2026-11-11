"""Bounded wire-level controlled-LLM HTTP/SSE test; never real LLM performance."""

import asyncio
import json
import math
import os
import platform
import statistics
import subprocess
import threading
import time
from pathlib import Path

import httpx

from research.docs.agent_engineering_upgrade.p4_dependency_integration.live_api import (
    LiveApi,
    snapshot,
)
from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import TOKENS

HERE = Path(__file__).parent


def usage(pid):
    raw = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()
    ticks = int(raw[11]) + int(raw[12])
    status = Path(f"/proc/{pid}/status").read_text().splitlines()
    memory = {
        x.split(":")[0]: int(x.split()[1]) for x in status if x.startswith(("VmRSS:", "VmHWM:"))
    }
    return {
        "cpu_s": ticks / os.sysconf("SC_CLK_TCK"),
        "rss_kib": memory["VmRSS"],
        "hwm_kib": memory["VmHWM"],
    }


def business(data):
    return {
        k: v for k, v in data.items() if k not in {"sessions", "messages", "pending_confirmations"}
    }


async def request(client, stream, index):
    started = time.perf_counter()
    events = []
    result = {"index": index, "transport": "SSE" if stream else "HTTP"}
    try:
        async with client.stream(
            "POST",
            "/api/v1/chat/stream" if stream else "/api/v1/chat",
            json={"message": "查询 ORD10001 的订单状态和金额"},
            headers={"authorization": "Bearer " + TOKENS["user"], "x-p4-case": "p4e_performance"},
        ) as response:
            result["headers_ms"] = (time.perf_counter() - started) * 1000
            result["status"] = response.status_code
            if stream:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        if not events:
                            result["first_event_ms"] = (time.perf_counter() - started) * 1000
                        events.append(json.loads(line[5:]))
                final = next((x["data"] for x in events if x["event"] == "answer"), {})
                valid = bool(
                    events
                    and events[-1]["event"] == "done"
                    and not any(x["event"] == "error" for x in events)
                )
                result["events"] = events
            else:
                await response.aread()
                final = response.json()
                valid = True
            result["answer"] = final.get("answer")
            result["session_id"] = final.get("session_id")
            result["success"] = (
                response.status_code == 200
                and valid
                and "299.00" in (result["answer"] or "")
                and "已发货" in result["answer"]
            )
    except Exception as exc:
        result.update(success=False, error_type=type(exc).__name__)
    result["latency_ms"] = (time.perf_counter() - started) * 1000
    return result


async def batch(url, stream, concurrency, pid):
    samples, stop = [], threading.Event()

    def monitor():
        while not stop.wait(0.05):
            samples.append(usage(pid))

    before = usage(pid)
    sampler = threading.Thread(target=monitor, daemon=True)
    sampler.start()
    try:
        async with httpx.AsyncClient(base_url=url, timeout=30, trust_env=False) as client:
            semaphore = asyncio.Semaphore(concurrency)

            async def bounded(index):
                async with semaphore:
                    return await request(client, stream, index)

            started = time.perf_counter()
            rows = await asyncio.gather(*(bounded(i) for i in range(12)))
            seconds = time.perf_counter() - started
        after = usage(pid)
    finally:
        stop.set()
        sampler.join(timeout=2)
    latencies = sorted(r["latency_ms"] for r in rows)
    successful = sum(r["success"] for r in rows)
    return {
        "transport": "SSE" if stream else "HTTP",
        "concurrency": concurrency,
        "n": len(rows),
        "success": successful,
        "errors": len(rows) - successful,
        "error_rate": 1 - successful / len(rows),
        "wall_s": seconds,
        "success_requests_per_s": successful / seconds,
        "latency_mean_ms": statistics.mean(latencies),
        "latency_p50_ms": statistics.median(latencies),
        "latency_p95_nearest_rank_ms": latencies[math.ceil(0.95 * len(rows)) - 1],
        "api_cpu_s": after["cpu_s"] - before["cpu_s"],
        "api_cpu_percent_one_core": 100 * (after["cpu_s"] - before["cpu_s"]) / seconds,
        "sample_interval_ms": 50,
        "resource_before": before,
        "resource_after": after,
        "max_sampled_rss_kib": max(x["rss_kib"] for x in [before, after] + samples),
        "rows": rows,
    }


def docker_stats(cfg):
    names = [cfg["project"] + "-" + s + "-1" for s in ["postgres", "redis", "qdrant"]]
    raw = subprocess.check_output(
        [
            "docker",
            "--host",
            "unix:///var/run/docker.sock",
            "stats",
            "--no-stream",
            "--format",
            "{{json .}}",
            *names,
        ],
        text=True,
    )
    return [json.loads(x) for x in raw.splitlines()]


def main():
    out = HERE / "evidence/e2_performance.json"
    assert (
        not out.exists()
    ), "preserve completed run; choose new ID and artifact for a new authorized run"
    run = LiveApi("ubuntu_E2_perf_20261111")
    result = {
        "profile": "CONTROLLED_LLM_REAL_TCP_REAL_PG_REDIS_QDRANT",
        "neural_models": False,
        "embedding": "test hash fixture, not neural evidence",
        "paid_requests": 0,
        "active": False,
        "host": {
            "system": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
        },
        "batches": [],
    }
    before = asyncio.run(snapshot(run.cfg))
    try:
        started = time.perf_counter()
        run.start(1)
        process = run.processes[0]
        pid, url = process["process"].pid, process["url"]
        result["process_start_to_health_ms"] = (time.perf_counter() - started) * 1000
        result["dependency_stats_before"] = docker_stats(run.cfg)

        async def first():
            async with httpx.AsyncClient(base_url=url, timeout=30, trust_env=False) as client:
                return [await request(client, False, -2), await request(client, True, -1)]

        result["first_requests_not_in_warm_statistics"] = asyncio.run(first())
        for stream in [False, True]:
            for concurrency in [1, 4]:
                result["batches"].append(asyncio.run(batch(url, stream, concurrency, pid)))
                out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        result["dependency_stats_after"] = docker_stats(run.cfg)
        after = asyncio.run(snapshot(run.cfg))
        result["business_tables_unchanged"] = business(before) == business(after)
        assert result["business_tables_unchanged"]
        assert all(r["success"] for r in result["first_requests_not_in_warm_statistics"])
        assert all(b["errors"] == 0 for b in result["batches"])
        result["limitations"] = [
            "n12 per cell; fixed read-only task; no production capacity/SLO conclusion",
            "one API process; stateful chat writes excluded from business-table equality only for sessions/messages",
            "no real neural or DeepSeek inference in measured loop",
            "CPU excludes dependencies/client; dependency docker stats are point samples",
            "startup is process-to-ready with host page cache uncontrolled, not machine cold start",
            "50ms sampler may miss short spikes; HWM is process lifetime",
        ]
    finally:
        run.stop()
        result["owned_cleanup"] = json.loads((run.directory / "owned_cleanup.json").read_text())
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            [
                {
                    k: b[k]
                    for k in [
                        "transport",
                        "concurrency",
                        "n",
                        "errors",
                        "latency_mean_ms",
                        "latency_p95_nearest_rank_ms",
                        "success_requests_per_s",
                        "max_sampled_rss_kib",
                    ]
                }
                for b in result["batches"]
            ]
        )
    )


if __name__ == "__main__":
    main()
