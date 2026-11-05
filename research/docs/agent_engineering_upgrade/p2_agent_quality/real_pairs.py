"""Source-paired P2-R experiment; all paid commands require an explicit frozen run.

Execute this absolute file in a fresh process with --source-root. Application and
evaluator imports bind to that root before the frozen P2-Q safety helpers load.
"""

# ruff: noqa: E402 -- source binding and tracing disable must precede application imports.
from __future__ import annotations

import argparse
import ast
import asyncio
import importlib.util
import json
import logging
import math
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

HARNESS_ROOT = Path(__file__).resolve().parents[4]
_bootstrap = argparse.ArgumentParser(add_help=False)
_bootstrap.add_argument("--source-root", type=Path)
_binding, _ = _bootstrap.parse_known_args()
SOURCE_ROOT = (_binding.source_root or HARNESS_ROOT).resolve()
sys.path.insert(0, str(SOURCE_ROOT))
for _name in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING", "LANGSMITH_TRACING"):
    os.environ[_name] = "false"

HELPERS = HARNESS_ROOT / "research/docs/agent_engineering_upgrade/p2_quality/real.py"
_spec = importlib.util.spec_from_file_location("_p2r_frozen_safety_helpers", HELPERS)
assert _spec and _spec.loader
old = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(old)
import httpx

SafetyStop, digest, read, write, exclusive = (
    old.SafetyStop,
    old.digest,
    old.read,
    old.write,
    old.exclusive,
)
LIMITS = {"requests": 420, "tokens": 420_000, "usd": 3.0}
GROUP_LIMIT = 24
BASE = "09819352cc6df98b9f8cb42ffb56e9c8365b5793"
DEV_IDS = ["dv01", "dv06", "dv08", "dv16", "dv18"]
ENV_FILE = Path("D:/Code/Adaptive-rag/.env")


class Ledger(old.Ledger):
    """A new P2-R namespace; never inherit the old 350/300k budget initializer."""

    def __init__(self, run, *, limits=None, pricing=None):
        self.run = Path(run).resolve()
        self.limits = LIMITS | (limits or {})
        if set(self.limits) != set(LIMITS) or any(
            not math.isfinite(self.limits[k]) or not 0 <= self.limits[k] <= v
            for k, v in LIMITS.items()
        ):
            raise SafetyStop("invalid P2-R hard budget")
        self.pricing = pricing or {"input": 0.30, "output": 1.20}
        if set(self.pricing) != {"input", "output"} or any(
            not math.isfinite(v) or v < 0 for v in self.pricing.values()
        ):
            raise SafetyStop("invalid frozen pricing")
        self.path = self.run / "requests.json"
        self.rows = read(self.path) if self.path.exists() else []
        if not isinstance(self.rows, list) or any(
            r.get("schema") != "p2r-request-v1" for r in self.rows
        ):
            raise SafetyStop("foreign or corrupt ledger; old P2-Q state must never be loaded")
        self.active_group = None
        self.metadata = {}

    def save(self):
        for row in self.rows:
            if row["group"] == self.active_group:
                for key, value in self.metadata.items():
                    row.setdefault(key, value)
        super().save()

    def totals(self):
        tokens, reported, usd = 0, 0, 0.0
        for row in self.rows:
            usage = old.usage(row.get("usage"))
            prompt = usage["prompt_tokens"] if usage else row["reserve_input"]
            completion = usage["completion_tokens"] if usage else row["reserve_output"]
            tokens += prompt + completion
            reported += usage["total_tokens"] if usage else 0
            usd += (
                prompt * self.pricing["input"] + completion * self.pricing["output"]
            ) / 1_000_000
        return dict(
            http_attempts=len(self.rows),
            accounted_tokens=tokens,
            reported_tokens=reported,
            estimated_usd=usd,
            unknown_usage_requests=sum(old.usage(r.get("usage")) is None for r in self.rows),
        )

    def forecast(self, requests, tokens, usd):
        if any(not math.isfinite(v) or v < 0 for v in (requests, tokens, usd)):
            raise SafetyStop("invalid budget forecast")
        if (
            self.active_group is not None
            and sum(r["group"] == self.active_group for r in self.rows) + requests > GROUP_LIMIT
        ):
            raise SafetyStop("per-group request budget exhausted")
        # The reused transport passes its original prices. A peak-price bound
        # remains conservative under this run's independently frozen pricing.
        super().forecast(
            requests, tokens, max(usd, tokens * max(self.pricing.values()) / 1_000_000)
        )


class _TimedTransport(httpx.AsyncBaseTransport):
    def __init__(self, owner, underlying):
        self.owner, self.underlying = owner, underlying

    async def handle_async_request(self, request):
        started = time.perf_counter()
        self.owner.live_attempts += 1
        try:
            response = await self.underlying.handle_async_request(request)
            await response.aread()
            return response
        except BaseException as exc:
            # The old transport's Exception handler subsequently saves too. This
            # checkpoint also covers KeyboardInterrupt/cancellation during HTTP.
            ledger = self.owner.ledger
            row = ledger.rows[-1]
            row.update(
                latency_ms=(time.perf_counter() - started) * 1000,
                failed_at=old.stamp(),
                transport_error_type=type(exc).__name__,
            )
            ledger.save()
            raise

    async def aclose(self):
        await self.underlying.aclose()


class Transport(old.ReplayTransport):
    """Reuse write-ahead/replay/whitelist logic, adding binding and crash timing."""

    def __init__(self, ledger, group, *, source_sha256, config_sha256, underlying=None):
        self.live_attempts = 0
        self.source_sha256, self.config_sha256 = source_sha256, config_sha256
        super().__init__(
            ledger, group, _TimedTransport(self, underlying or httpx.AsyncHTTPTransport(retries=0))
        )

    async def handle_async_request(self, request):
        for row in self.ledger.rows:
            if row["group"] == self.group and (
                row.get("source_sha256") != self.source_sha256
                or row.get("config_sha256") != self.config_sha256
            ):
                raise SafetyStop("source/config fingerprint hash conflict; replay forbidden")
        body = json.loads(request.content)
        self.ledger.active_group = self.group
        self.ledger.metadata = dict(
            schema="p2r-request-v1",
            source_sha256=self.source_sha256,
            config_sha256=self.config_sha256,
            expects_json=body.get("response_format", {}).get("type") == "json_object",
        )
        return await super().handle_async_request(request)


class Provider(old.Provider):
    def __init__(self, settings, ledger, group, *, source_sha256, config_sha256):
        frozen = settings.model_copy(update={"llm_max_retries": 1, "llm_timeout_seconds": 30.0})
        self.client = httpx.AsyncClient(
            base_url=frozen.deepseek_base_url.rstrip("/"),
            timeout=30,
            transport=Transport(
                ledger, group, source_sha256=source_sha256, config_sha256=config_sha256
            ),
        )
        old.DeepSeekProvider.__init__(self, frozen, client=self.client)

    async def generate(self, messages, *, temperature=0.0, max_tokens=1024, response_format=None):
        return await super().generate(
            messages,
            temperature=0,
            max_tokens=min(max_tokens, 1024),
            response_format=response_format,
        )


def verify_fingerprint(expected, actual):
    if digest(expected) != digest(actual):
        raise SafetyStop("frozen source/config fingerprint hash conflict")


def bound_imports():
    import app.config.settings
    import eval.multiturn

    value = {
        "app_settings": str(Path(app.config.settings.__file__).resolve()),
        "eval_multiturn": str(Path(eval.multiturn.__file__).resolve()),
    }
    if any(not Path(p).is_relative_to(SOURCE_ROOT) for p in value.values()):
        raise SafetyStop("application/evaluator imported from wrong source root")
    return value


def source_files(root):
    return {
        p.relative_to(root).as_posix(): digest(p.read_bytes())
        for directory in ("app", "eval", "knowledge")
        for p in sorted((root / directory).rglob("*"))
        if p.is_file() and p.suffix in {".py", ".json", ".md", ".yaml", ".yml"}
    }


def output_caps(root):
    """Freeze call-site cap expressions, excluding line numbers and prompt text."""
    result = {}
    for p in sorted((root / "app").rglob("*.py")):
        values = {
            ast.dump(k.value, include_attributes=False)
            for node in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
            if isinstance(node, ast.Call)
            for k in node.keywords
            if k.arg == "max_tokens"
        }
        if values:
            result[p.relative_to(root).as_posix()] = sorted(values)
    return result


def safe_settings_hash(settings):
    # Include credential identity as a one-way hash; neither key nor masked
    # settings text is serialized into the run configuration.
    value = json.loads(settings.model_dump_json())
    for name in type(settings).model_fields:
        field = getattr(settings, name)
        if hasattr(field, "get_secret_value"):
            value[name] = digest(field.get_secret_value().encode())
    return digest(value)


def clean_source_head(root):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", "app", "eval", "knowledge"], cwd=root
    ).returncode:
        raise SafetyStop("source snapshot must be clean at its frozen commit")
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "app", "eval", "knowledge"],
        cwd=root,
        text=True,
    )
    if any(
        Path(p).suffix in {".py", ".json", ".md", ".yaml", ".yml"} for p in untracked.splitlines()
    ):
        raise SafetyStop("source snapshot contains uncommitted source files")
    return head


def fingerprint(env_file):
    imports = bound_imports()
    settings = old.settings(str(env_file))
    url = urlsplit(settings.deepseek_base_url)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.query
        or url.fragment
    ):
        raise SafetyStop("provider endpoint must be public HTTPS without embedded credentials")
    files = source_files(SOURCE_ROOT)
    return dict(
        head=clean_source_head(SOURCE_ROOT),
        files=files,
        source_sha256=digest(files),
        imports=imports,
        provider_settings_sha256=safe_settings_hash(settings),
        ambient_settings_sha256=safe_settings_hash(old.Settings(_env_file=None)),
        endpoint=settings.deepseek_base_url,
        model=settings.deepseek_model,
        key_recognized=settings.llm_configured,
        caps=output_caps(SOURCE_ROOT),
        prompts={p: h for p, h in files.items() if p.startswith("app/prompts/")},
    )


def worker_snapshot(source_root, env_file):
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_snapshot",
        "--source-root",
        str(source_root),
        "--env-file",
        str(env_file),
    ]
    completed = subprocess.run(command, cwd=source_root, capture_output=True, text=True)
    if completed.returncode:
        raise SafetyStop(
            "source worker fingerprint failed; inspect source/environment without exposing credentials"
        )
    return json.loads(completed.stdout)


def select_blind(ids):
    if len(set(ids)) < 6:
        raise SafetyStop("six distinct blind case IDs required")
    return sorted(set(ids), key=lambda case: (digest(("P2R-20261105" + case).encode()), case))[:6]


def dataset_ids(path):
    # ID-only selection. No query/Gold/result participates in the experiment plan.
    value = read(path)
    ids = [row["id"] for row in value["scenarios"]]
    if value["schema_version"] != "agent-scenarios-v2.1" or len(ids) != len(set(ids)):
        raise SafetyStop("invalid dataset schema or duplicate IDs")
    return ids


def prepare(args):
    run = args.run_dir.resolve()
    if any(p.name != ".lock" for p in run.iterdir()):
        raise SafetyStop("prepare cannot overwrite an existing experiment")
    roots = {"R0": args.r0_root.resolve(), "R1": args.r1_root.resolve()}
    snapshots = {v: worker_snapshot(root, args.env_file.resolve()) for v, root in roots.items()}
    if snapshots["R0"]["head"] != BASE or snapshots["R1"]["head"] != args.candidate_commit:
        raise SafetyStop("baseline or candidate frozen commit mismatch")
    for key in ("provider_settings_sha256", "ambient_settings_sha256", "endpoint", "model", "caps"):
        if snapshots["R0"][key] != snapshots["R1"][key]:
            raise SafetyStop("source pairs differ in common settings/output caps")
    common = [
        p
        for p in snapshots["R0"]["files"]
        if p.startswith(("eval/", "knowledge/")) or p == "app/services/seed.py"
    ]
    if any(snapshots["R0"]["files"][p] != snapshots["R1"]["files"].get(p) for p in common):
        raise SafetyStop("source pairs differ in evaluator/Gold/knowledge/seed fixtures")
    datasets = {"development": args.dev_dataset.resolve(), "blind": args.blind_dataset.resolve()}
    ids = {split: dataset_ids(path) for split, path in datasets.items()}
    dev = []
    for name in DEV_IDS:
        matches = [
            case
            for case in ids["development"]
            if case == name or case.endswith("-" + name) or case.endswith("_" + name)
        ]
        if len(matches) != 1:
            raise SafetyStop("predeclared development ID absent or ambiguous")
        dev.append(matches[0])
    if len(ids["blind"]) != 33:
        raise SafetyStop("frozen full blind denominator must remain 33")
    if not args.pricing_url.startswith("https://") or not args.pricing_verified_date:
        raise SafetyStop("explicit verified pricing source/date required")
    selected = [{"id": case, "split": "development"} for case in dev] + [
        {"id": case, "split": "blind"} for case in select_blind(ids["blind"])
    ]
    prompts = set(snapshots["R0"]["prompts"]) | set(snapshots["R1"]["prompts"])
    config = dict(
        schema="p2r-real-pairs-v1",
        created_at=old.stamp(),
        project_root=str(args.project_root.resolve()),
        roots={v: str(p) for v, p in roots.items()},
        snapshots=snapshots,
        harness_sha256=digest(Path(__file__).read_bytes()),
        helpers_sha256=digest(HELPERS.read_bytes()),
        datasets={
            s: {"path": str(p), "sha256": digest(p.read_bytes()), "case_count": len(ids[s])}
            for s, p in datasets.items()
        },
        selected=selected,
        selection_rule="sha256('P2R-20261105'+case_id), first six, IDs only; five predeclared development IDs",
        mode="M2",
        public_cross_session_M3="OFF",
        database="fresh isolated SQLite memory per group",
        seed_clock=old.stamp(),
        temperature=0,
        output_maximum=1024,
        per_group_http_limit=GROUP_LIMIT,
        http_attempts_per_generation=1,
        llm_max_retries=1,
        concurrency=1,
        repetitions=[0, 1],
        limits=LIMITS,
        env_file=str(args.env_file.resolve()),
        pricing={"input": args.input_price, "output": args.output_price},
        pricing_url=args.pricing_url,
        pricing_verified_date=args.pricing_verified_date,
        prompt_differences={
            p: {v: snapshots[v]["prompts"].get(p) for v in roots}
            for p in sorted(prompts)
            if snapshots["R0"]["prompts"].get(p) != snapshots["R1"]["prompts"].get(p)
        },
    )
    Ledger(run, pricing=config["pricing"])
    config["config_sha256"] = digest(config)
    write(run / "experiment_config.json", config)
    write(run / "requests.json", [])
    write(run / "results.json", {"probe": None, "groups": [], "status": "PREPARED"})
    return dict(
        status="PREPARED", selected_groups=len(selected) * 2, blind_cases=33, paid_http_attempts=0
    )


def verify(run, env_file, variant):
    config = read(run / "experiment_config.json")
    if digest({k: v for k, v in config.items() if k != "config_sha256"}) != config["config_sha256"]:
        raise SafetyStop("experiment config hash conflict")
    if (
        config["limits"] != LIMITS
        or config["per_group_http_limit"] != GROUP_LIMIT
        or config["mode"] != "M2"
        or digest(Path(__file__).read_bytes()) != config["harness_sha256"]
        or digest(HELPERS.read_bytes()) != config["helpers_sha256"]
        or str(env_file.resolve()) != config["env_file"]
        or str(SOURCE_ROOT) != config["roots"][variant]
    ):
        raise SafetyStop("harness/source/config fingerprint conflict")
    verify_fingerprint(config["snapshots"][variant], fingerprint(env_file))
    for dataset in config["datasets"].values():
        if digest(Path(dataset["path"]).read_bytes()) != dataset["sha256"]:
            raise SafetyStop("frozen dataset hash conflict")
    return config, old.settings(str(env_file))


def analyze_response(row):
    result = {"lexical_error": None, "schema_error": None}
    if not row.get("expects_json"):
        return result
    try:
        value = json.loads(row["response"]["choices"][0]["message"]["content"])
        if not isinstance(value, dict):
            raise ValueError
    except (ValueError, TypeError, KeyError, IndexError):
        result["lexical_error"] = "invalid_json_object"
        return result
    from app.schemas.agent import AgentPlan, ComplexityResult, IntentResult

    models = {"intent": IntentResult, "router": ComplexityResult, "planner": AgentPlan}
    stage = row.get("stage")
    try:
        if stage in models:
            models[stage].model_validate(value)
        elif stage in {"generate", "self_correct"}:
            assert isinstance(value.get("answer"), str)
            assert isinstance(value.get("citation_chunk_ids"), list) and all(
                isinstance(c, str) for c in value["citation_chunk_ids"]
            )
            if stage == "generate":
                assert type(value.get("refused")) is bool
        elif stage == "judge":
            assert value.get("status") in {"SUPPORTED", "UNSUPPORTED", "INSUFFICIENT_EVIDENCE"}
            assert type(value.get("supported")) is bool
            assert isinstance(value.get("hallucinated_spans"), list)
    except (ValueError, TypeError, AssertionError):
        result["schema_error"] = "invalid_" + str(stage) + "_schema"
    return result


def attach_provenance(raw, rows, *, variant, rep, live_attempts):
    errors = [
        dict(
            sequence=r.get("sequence"),
            stage=r.get("stage"),
            model_error=r.get("model_error"),
            **analyze_response(r),
        )
        for r in rows
    ]
    return dict(
        raw,
        raw_driver_result=dict(raw),
        variant=variant,
        rep=rep,
        mode="M2",
        model_evaluation="REAL_PROVIDER" if rows else "NO_HTTP_FOR_GROUP",
        evidence_origin="REAL_PROVIDER_COMPLETIONS"
        if live_attempts
        else "COMPLETED_RESPONSE_REPLAY"
        if rows
        else "REAL_PROVIDER_CONFIGURED_NO_HTTP",
        http_attempts=len(rows),
        new_http_attempts=live_attempts,
        request_errors=[
            e for e in errors if e["model_error"] or e["lexical_error"] or e["schema_error"]
        ],
    )


def summary(result, ledger):
    groups = result["groups"]
    arms = {}
    for variant in ("R0", "R1"):
        rows = [g for g in groups if g["variant"] == variant]
        valid = [g for g in rows if not g["request_errors"] and g["status"] != "ERROR"]
        arms[variant] = dict(
            attempted_groups=len(rows),
            passed=sum(g["status"] == "PASS" for g in rows),
            task_success_including_errors=sum(g["status"] == "PASS" for g in rows) / len(rows)
            if rows
            else None,
            task_success_valid_outputs=sum(g["status"] == "PASS" for g in valid) / len(valid)
            if valid
            else None,
            lexical_error_groups=sum(
                any(e["lexical_error"] for e in g["request_errors"]) for g in rows
            ),
            schema_error_groups=sum(
                any(e["schema_error"] for e in g["request_errors"]) for g in rows
            ),
        )
    pairs = {(g["case_id"], g["rep"]) for g in groups}
    complete = [
        pair
        for pair in pairs
        if {g["variant"] for g in groups if (g["case_id"], g["rep"]) == pair} == {"R0", "R1"}
    ]
    diagnostics = [analyze_response(row) for row in ledger.rows]
    return dict(
        arms=arms,
        completed_source_pairs=len(complete),
        requests=ledger.totals(),
        request_diagnostics=dict(
            lexical_errors=sum(bool(d["lexical_error"]) for d in diagnostics),
            schema_errors=sum(bool(d["schema_error"]) for d in diagnostics),
            http_errors=sum(str(r.get("model_error", "")).startswith("http_") for r in ledger.rows),
            truncations=sum(r.get("model_error") == "truncated" for r in ledger.rows),
            transport_failures=sum(bool(r.get("transport_error_type")) for r in ledger.rows),
            latency_observations=sum("latency_ms" in r for r in ledger.rows),
            schema_checked_stages=[
                "intent",
                "router",
                "planner",
                "generate",
                "self_correct",
                "judge",
            ],
        ),
        limits=ledger.limits,
        pricing="Frozen peak prices, no cache discounts; estimate is not invoice",
        model_evaluation="REAL_PROVIDER_EXPERIMENT",
    )


async def execute(args):
    run = args.run_dir.resolve()
    config, settings = verify(run, args.env_file, args.variant)
    if not settings.llm_configured:
        raise SafetyStop("explicit env file has no configured provider key")
    result = read(run / "results.json")
    ledger = Ledger(run, pricing=config["pricing"])
    ledger.check_pending()
    if args.command == "probe":
        if result["probe"] is not None:
            raise SafetyStop("probe already completed; never repeat automatically")
        group_name = "__probe__:" + args.variant + ":0"
    else:
        if not result["probe"] or not result["probe"].get("completion_valid"):
            raise SafetyStop("one successful bounded probe is required")
        selected = {case["id"]: case["split"] for case in config["selected"]}
        if args.case_id not in selected or args.rep not in (0, 1):
            raise SafetyStop("group absent from the frozen plan")
        if any(
            g["case_id"] == args.case_id and g["variant"] == args.variant and g["rep"] == args.rep
            for g in result["groups"]
        ):
            return dict(status="ALREADY_COMPLETED", **ledger.totals())
        pilot = config["selected"][0]["id"]
        if args.case_id != pilot or args.rep:
            if {
                g["variant"] for g in result["groups"] if g["case_id"] == pilot and g["rep"] == 0
            } != {"R0", "R1"}:
                raise SafetyStop(
                    "complete and inspect the first development source pair before continuation"
                )
        if args.rep:
            if not all(
                any(
                    g["case_id"] == args.case_id and g["variant"] == v and g["rep"] == 0
                    for g in result["groups"]
                )
                for v in ("R0", "R1")
            ):
                raise SafetyStop("a repeat requires the whole initial source pair")
        group_name = args.case_id + ":" + args.variant + ":" + str(args.rep)
        if not any(r["group"] == group_name for r in ledger.rows):
            pair_not_started = args.rep and not any(
                g["case_id"] == args.case_id and g["rep"] == args.rep for g in result["groups"]
            )
            multiplier = 2 if pair_not_started else 1
            ledger.forecast(
                multiplier * GROUP_LIMIT,
                multiplier * 24000,
                multiplier * 24000 * max(config["pricing"].values()) / 1_000_000,
            )
    provider = Provider(
        settings,
        ledger,
        group_name,
        source_sha256=config["snapshots"][args.variant]["source_sha256"],
        config_sha256=config["config_sha256"],
    )
    try:
        if args.command == "probe":
            try:
                response = await provider.generate(
                    [{"role": "user", "content": "Reply exactly P2R_OK."}], max_tokens=32
                )
                value = dict(
                    connected=True,
                    completion_valid=response.content.strip() == "P2R_OK",
                    model=response.model,
                )
            except Exception as exc:
                value = dict(connected=False, completion_valid=False, error_type=type(exc).__name__)
            result["probe"] = value
        else:
            split = selected[args.case_id]
            dataset = config["datasets"][split]
            cases, dataset_hash = old.load_scenarios(Path(dataset["path"]))
            case = next(c for c in cases if c.id == args.case_id)

            def environment(**kwargs):
                return old.BusinessEnvironment(memory_mode="M2", **kwargs)

            with (
                patch("eval.multiturn.BusinessEnvironment", environment),
                patch(
                    "app.services.seed.utcnow",
                    return_value=datetime.fromisoformat(config["seed_clock"]),
                ),
            ):
                scored = await old.run_scenarios(
                    [case], dataset_sha256=dataset_hash, tracing=False, llm_factory=lambda: provider
                )
            rows = [r for r in ledger.rows if r["group"] == group_name]
            if provider.client._transport.sequence != len(rows):
                raise SafetyStop("replay ended before frozen request sequence")
            value = attach_provenance(
                scored[0].model_dump(mode="json"),
                rows,
                variant=args.variant,
                rep=args.rep,
                live_attempts=provider.client._transport.live_attempts,
            )
            value.update(
                split=split,
                source_sha256=config["snapshots"][args.variant]["source_sha256"],
                group=group_name,
            )
            if any(str(e["model_error"]).startswith("http_") for e in value["request_errors"]):
                value["status"] = "ERROR"
            result["groups"].append(value)
        verify(run, args.env_file, args.variant)
        result["status"] = "RUNNING"
        result["summary"] = summary(result, ledger)
        write(run / "results.json", result)
        return dict(
            status=value.get("status", "PROBE_COMPLETE"), group=group_name, **ledger.totals()
        )
    finally:
        await provider.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["prepare", "probe", "run-group", "summary", "_snapshot", "_imports"]
    )
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--project-root", type=Path, default=HARNESS_ROOT)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--r0-root", type=Path)
    parser.add_argument("--r1-root", type=Path)
    parser.add_argument("--candidate-commit")
    parser.add_argument("--dev-dataset", type=Path)
    parser.add_argument("--blind-dataset", type=Path)
    parser.add_argument("--variant", choices=["R0", "R1"], default="R0")
    parser.add_argument("--case-id")
    parser.add_argument("--rep", type=int, default=0)
    parser.add_argument("--input-price", type=float)
    parser.add_argument("--output-price", type=float)
    parser.add_argument("--pricing-url")
    parser.add_argument("--pricing-verified-date")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        if args.command in {"_snapshot", "_imports"}:
            value = fingerprint(args.env_file) if args.command == "_snapshot" else bound_imports()
        else:
            if args.run_dir is None:
                parser.error("--run-dir is required")
            if args.command == "prepare":
                required = (
                    args.r0_root,
                    args.r1_root,
                    args.candidate_commit,
                    args.dev_dataset,
                    args.blind_dataset,
                    args.input_price,
                    args.output_price,
                    args.pricing_url,
                    args.pricing_verified_date,
                )
                if any(v is None for v in required):
                    parser.error(
                        "prepare requires both source roots, candidate commit, datasets and verified pricing"
                    )
                args.run_dir.resolve().mkdir(parents=True, exist_ok=False)
            with exclusive(args.run_dir.resolve()):
                if args.command == "prepare":
                    value = prepare(args)
                elif args.command == "summary":
                    config = read(args.run_dir / "experiment_config.json")
                    value = summary(
                        read(args.run_dir / "results.json"),
                        Ledger(args.run_dir, pricing=config["pricing"]),
                    )
                else:
                    value = asyncio.run(execute(args))
        print(json.dumps(value, ensure_ascii=True, indent=2))
    except SafetyStop as exc:
        print("STOP: " + str(exc))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
