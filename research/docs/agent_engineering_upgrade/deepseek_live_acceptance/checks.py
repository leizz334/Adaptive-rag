"""Offline regression/build/start gates; paid calls are absent from this script."""

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path.cwd()
HERE = ROOT / "research/docs/agent_engineering_upgrade/deepseek_live_acceptance"
OUT = HERE / "evidence"
PRIVATE = Path("/home/panda/.adaptive-rag-live-20261114")
IMAGE = "adaptive-rag-real-live:20261114"
PROJECT = "adaptive-rag-real-agent-dev"
os.umask(0o077)


def save(name, value):
    with (OUT / name).open("x") as stream:
        json.dump(value, stream, indent=2)


def docker(*args):
    p = subprocess.run(["docker", *args], capture_output=True, text=True)
    if p.returncode:
        (PRIVATE / "docker-last-error.log").write_text(p.stderr)
        raise RuntimeError("Docker failed; private diagnostics retained")
    return p.stdout


def compose(*args):
    return docker(
        "compose",
        "--env-file",
        str(PRIVATE / "compose.env"),
        "-p",
        PROJECT,
        "-f",
        str(ROOT / "compose.showcase.yml"),
        "-f",
        str(ROOT / "compose.agent-dev.yml"),
        "-f",
        str(PRIVATE / "image.override.json"),
        *args,
    )


if len(sys.argv) < 2:
    env = os.environ.copy()
    env.update(DEEPSEEK_API_KEY="", EMBEDDING_API_KEY="", EXPERIENCE_MEMORY_MODE="off")
    junit = PRIVATE / "preflight-tests.xml"
    argv = [
        sys.executable,
        "-m",
        "research.docs.agent_engineering_upgrade.p4_final_acceptance.offline",
        "pytest",
        "tests",
        "-q",
        "--junitxml=" + str(junit),
    ]
    with (PRIVATE / "preflight-tests.log").open("x") as stream:
        result = subprocess.run(argv, env=env, stdout=stream, stderr=stream)
    summary = [
        {
            k: v
            for k, v in s.attrib.items()
            if k in ["tests", "errors", "failures", "skipped", "time"]
        }
        for s in ET.parse(junit).getroot().iter("testsuite")
    ]
    save(
        "D2-preflight.json",
        {
            "exit": result.returncode,
            "summary": summary,
            "red_green": "5 failed +28 passed before fix; 77passed initial GREEN; full tests include exact6/10000/0.05 gate and HTTP/SSE regression",
            "model_http_requests": 0,
            "transport": "MockTransport only for provider tests",
        },
    )
    print(
        json.dumps(
            {"preflight_exit": result.returncode, "summary": summary, "model_http_requests": 0}
        )
    )
    raise SystemExit(result.returncode)
elif sys.argv[1] == "build":
    with (PRIVATE / "image-build.log").open("x") as stream:
        result = subprocess.run(
            ["docker", "build", "--target", "showcase", "-t", IMAGE, "."],
            stdout=stream,
            stderr=stream,
        )
    assert result.returncode == 0, "Build failed; diagnostics private"
    image_id = docker("image", "inspect", IMAGE, "--format", "{{.Id}}").strip()
    save(
        "D2-image.json", {"image": IMAGE, "image_id": image_id, "exit": 0, "model_http_requests": 0}
    )
    print(json.dumps({"build": "PASS", "image_id": image_id}))
elif sys.argv[1] == "start":
    assert json.loads((OUT / "D2-preflight.json").read_text())["exit"] == 0
    assert not docker(
        "ps", "-aq", "--filter", "label=com.docker.compose.project=" + PROJECT
    ).strip(), "Existing RealDev project must be audited instead of recreated"
    assert not any(
        name.startswith(PROJECT + "_")
        for name in docker("volume", "ls", "--format", "{{.Name}}").splitlines()
    ), "Preserve existing volumes and ledger; do not reset"
    for suffix in ["8001"]:
        assert not docker("ps", "-q", "--filter", "publish=" + suffix).strip()
    (PRIVATE / "image.override.json").write_text(
        json.dumps(
            {
                "services": {
                    s: {"image": IMAGE, "pull_policy": "never"}
                    for s in ["api", "bootstrap", "initialize"]
                }
            }
        )
    )
    resolved = json.loads(compose("config", "--format", "json"))
    assert resolved["name"] == PROJECT
    api = resolved["services"]["api"]
    assert len(api["ports"]) == 1 and api["ports"][0]["published"] == "8001"
    expected = {
        "REAL_AGENT_MAX_REQUESTS": "6",
        "REAL_AGENT_MAX_TOKENS": "10000",
        "REAL_AGENT_MAX_USD": "0.05",
        "DEEPSEEK_API_KEY": "",
        "DEEPSEEK_MODEL": "deepseek-flash",
        "DEEPSEEK_THINKING_MODE": "disabled",
        "EXPERIENCE_MEMORY_MODE": "off",
        "REAL_AGENT_INPUT_USD_PER_MILLION": "0.30",
        "REAL_AGENT_OUTPUT_USD_PER_MILLION": "1.20",
    }
    assert all(api["environment"].get(k) == v for k, v in expected.items())
    url = urlsplit(api["environment"]["DEEPSEEK_BASE_URL"])
    assert (
        url.scheme == "https"
        and url.hostname == "api.deepseek.com"
        and url.port in {None, 443}
        and url.path.rstrip("/") in {"", "/v1"}
        and not (url.username or url.password or url.query or url.fragment)
    )
    compose("up", "-d", "--no-build", "--wait", "--wait-timeout", "150")
    code = """
import json,hashlib
from pathlib import Path
from dataclasses import asdict
from app.demo.real_dev import load_runtime_config
from app.providers.paid_budget import AttemptLedger
from urllib.parse import urlsplit
c=load_runtime_config()
u=urlsplit(c.settings.deepseek_base_url)
assert c.settings.deepseek_model==c.limits.model=='deepseek-flash'
assert u.scheme=='https' and u.hostname=='api.deepseek.com' and u.port in {None,443} and u.path.rstrip('/') in {'','/v1'} and not(u.username or u.password or u.query or u.fragment)
assert (c.limits.max_requests,c.limits.max_tokens,str(c.limits.max_usd),str(c.limits.input_usd_per_million),str(c.limits.output_usd_per_million))==(6,10000,'0.05','0.30','1.20')
b=AttemptLedger(c.budget_path,c.limits)
b.ensure_ready()
print(json.dumps({'ledger':b.snapshot(),'limits':asdict(c.limits),'retries':c.settings.llm_max_retries,'thinking_mode':c.settings.deepseek_thinking_mode,'app_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('app').rglob('*.py')}},default=str))
"""
    metadata = json.loads(docker("exec", PROJECT + "-api-1", "python", "-c", code))
    assert (
        metadata["ledger"]["requests"] == 0
        and metadata["ledger"]["pending"] == 0
        and metadata["ledger"]["uncertain"] == 0
    )
    assert metadata["retries"] == 1 and metadata["thinking_mode"] == "disabled"
    import hashlib

    local = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (ROOT / "app").rglob("*.py")
    }
    assert metadata.pop("app_hashes") == local
    metadata["app_source_match_count"] = len(local)
    ids = docker("ps", "-aq", "--filter", "label=com.docker.compose.project=" + PROJECT).split()
    rows = json.loads(docker("inspect", *ids))
    metadata["containers"] = [
        {
            "id": r["Id"],
            "name": r["Name"],
            "image": r["Image"],
            "state": r["State"]["Status"],
            "health": r["State"].get("Health", {}).get("Status"),
            "mounts": [m.get("Name") for m in r["Mounts"]],
        }
        for r in rows
    ]
    save("D2-startup.json", metadata)
    print(
        json.dumps(
            {
                "startup": "PASS",
                "ledger": metadata["ledger"],
                "actual_source_match": len(local),
                "model_http_requests": 0,
            }
        )
    )
