"""Bounded P2-S source-pair experiment. Import and preparation never send HTTP.

Use a fresh process and --source-root for every arm. Frozen historical helpers
are loaded by absolute path only after that application source has been bound.
"""

# ruff: noqa: E402 -- source binding must precede application imports.
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
from contextlib import ExitStack, contextmanager, nullcontext
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
HARNESS_ROOT = HERE.parents[3]
_bootstrap = argparse.ArgumentParser(add_help=False)
_bootstrap.add_argument("--source-root", type=Path)
_bootstrap.add_argument("--freeze-file", type=Path)
_bootstrap.add_argument("--run-dir", type=Path)
_binding, _ = _bootstrap.parse_known_args()
SOURCE_ROOT = (_binding.source_root or HARNESS_ROOT).resolve()
sys.path.insert(0, str(SOURCE_ROOT))
for _name in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_TRACING", "LANGSMITH_TRACING"):
    os.environ[_name] = "false"


def absolute_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError("Cannot load frozen experiment helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R5_HELPER = HERE.parent / "p2_agent_quality/real_pairs.py"
Q_HELPER = HERE.parent / "p2_quality/real.py"
INSTRUMENTATION = HERE.parent / "p2_agent_quality/instrumented.py"
SCORER = HARNESS_ROOT / "eval/answer_scoring.py"
_config_path = _binding.run_dir / "experiment_config.json" if _binding.run_dir else None
_configured_freeze = (
    json.loads(_config_path.read_bytes()).get("freeze_file")
    if _config_path and _config_path.exists()
    else None
)
FREEZE = (
    _binding.freeze_file or Path(_configured_freeze or HERE / "evidence/candidate_freeze.json")
).resolve()
r5 = absolute_module("_p2s_frozen_r5_helpers", R5_HELPER)
old = r5.old
SafetyStop, digest, read, write, exclusive = (
    old.SafetyStop,
    old.digest,
    old.read,
    old.write,
    old.exclusive,
)
import httpx

LIMITS = {"requests": 350, "tokens": 300_000, "usd": 3.0}
GROUP_LIMIT = 24
BASE = "e74f01db65fb9f3df929cdf5932919e1f10e453e"
DEV_IDS = ["PSD03", "PSD05", "PSD08", "PSD10"]
ENV_FILE = Path("D:/Code/Adaptive-rag/.env")


class Ledger(r5.Ledger):
    """Never inherit the R5 initializer's 420-request/420k-token namespace."""

    def __init__(self, run, *, limits=None, pricing=None):
        self.run = Path(run).resolve()
        self.limits = LIMITS | (limits or {})
        if set(self.limits) != set(LIMITS) or any(
            type(self.limits[k]) not in (int, float)
            or not math.isfinite(self.limits[k])
            or not 0 <= self.limits[k] <= bound
            for k, bound in LIMITS.items()
        ):
            raise SafetyStop("invalid P2-S hard budget")
        self.pricing = pricing or {"input": 0.30, "output": 1.20}
        if set(self.pricing) != {"input", "output"} or any(
            type(v) not in (int, float) or not math.isfinite(v) or v < 0
            for v in self.pricing.values()
        ):
            raise SafetyStop("invalid frozen pricing")
        self.path = self.run / "requests.json"
        self.rows = read(self.path) if self.path.exists() else []
        if not isinstance(self.rows, list) or any(
            not isinstance(row, dict) or row.get("schema") != "p2s-request-v1" for row in self.rows
        ):
            raise SafetyStop("foreign or corrupt ledger schema; never load P2-Q/P2-R pending")
        self.active_group, self.metadata, self.inflight = None, {}, False
        self._check_ancestry()

    def _check_ancestry(self):
        config_path = self.run / "experiment_config.json"
        if config_path.exists() and (history := read(config_path).get("history_ancestor")):
            parent_config, inherited, _ = read_ancestor(history["root"], expected=history)
            if self.pricing != parent_config["pricing"]:
                raise SafetyStop("ancestor pricing conflict; spent requests cannot be repriced")
            if self.rows[: len(inherited)] != inherited:
                raise SafetyStop("ancestor rows missing, mutated or deduplicated incorrectly")
            ancestor_groups = {row["group"] for row in inherited}
            if any(row["group"] in ancestor_groups for row in self.rows[len(inherited) :]):
                raise SafetyStop("ancestor row/group duplication conflict")

    def check_pending(self):
        self._check_ancestry()
        super().check_pending()
        if any(old.usage(row.get("usage")) is None for row in self.rows):
            raise SafetyStop("unknown response usage reserved; stop further paid dispatch")


class Transport(old.ReplayTransport):
    """Original durable reservation/public replay plus R5 BaseException timing."""

    def __init__(self, ledger, group, *, source_sha256, config_sha256, underlying=None):
        self.live_attempts = 0
        self.source_sha256, self.config_sha256 = source_sha256, config_sha256
        super().__init__(
            ledger,
            group,
            r5._TimedTransport(self, underlying or httpx.AsyncHTTPTransport(retries=0)),
        )

    async def handle_async_request(self, request):
        if self.ledger.inflight:
            raise SafetyStop("concurrency must remain one")
        for row in self.ledger.rows:
            if row["group"] == self.group and (
                row.get("source_sha256") != self.source_sha256
                or row.get("config_sha256") != self.config_sha256
            ):
                raise SafetyStop("source/config fingerprint hash conflict; replay forbidden")
        body = json.loads(request.content)
        self.ledger.active_group = self.group
        self.ledger.metadata = dict(
            schema="p2s-request-v1",
            source_sha256=self.source_sha256,
            config_sha256=self.config_sha256,
            expects_json=body.get("response_format", {}).get("type") == "json_object",
        )
        self.ledger.inflight = True
        try:
            response = await super().handle_async_request(request)
            if response.status_code != 200:
                raise SafetyStop("HTTP error response saved; stop without retries")
            return response
        finally:
            self.ledger.inflight = False


class Provider(r5.Provider):
    def __init__(self, settings, ledger, group, *, source_sha256, config_sha256):
        frozen = settings.model_copy(
            update={
                "llm_max_retries": 1,
                "llm_timeout_seconds": 30.0,
                "agent_tracing_enabled": False,
            }
        )
        self.client = httpx.AsyncClient(
            base_url=frozen.deepseek_base_url.rstrip("/"),
            timeout=30,
            transport=Transport(
                ledger, group, source_sha256=source_sha256, config_sha256=config_sha256
            ),
        )
        old.DeepSeekProvider.__init__(self, frozen, client=self.client)


def helper_hashes(freeze_file=None):
    return {
        str(p.resolve()): digest(p.read_bytes())
        for p in (
            Path(__file__),
            R5_HELPER,
            Q_HELPER,
            INSTRUMENTATION,
            SCORER,
            freeze_file or FREEZE,
        )
    }


def signature_caps(root):
    """Include actual signature defaults; call-site AST alone misses Judge caps."""
    result = {}
    for path in sorted((root / "app").rglob("*.py")):
        values = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                pairs = (
                    list(
                        zip(
                            [*node.args.posonlyargs, *node.args.args][-len(node.args.defaults) :],
                            node.args.defaults,
                            strict=True,
                        )
                    )
                    if node.args.defaults
                    else []
                )
                pairs += list(zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True))
                values += [
                    node.name + ":" + ast.dump(default, include_attributes=False)
                    for arg, default in pairs
                    if arg.arg == "max_tokens" and default is not None
                ]
        if values:
            result[path.relative_to(root).as_posix()] = sorted(values)
    return result


def fingerprint(env_file):
    value = r5.fingerprint(env_file)
    value["signature_caps"] = signature_caps(SOURCE_ROOT)
    value["provider_class"] = "p2s.real_pairs.Provider"
    value["underlying_provider"] = str(
        Path(sys.modules[old.DeepSeekProvider.__module__].__file__).resolve()
    )
    return value


def worker_snapshot(root, env_file):
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "_snapshot",
            "--source-root",
            str(root),
            "--env-file",
            str(env_file),
        ],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise SafetyStop(
            "source snapshot worker failed; inspect locally without exposing credentials"
        )
    return json.loads(completed.stdout)


def select_blind(ids):
    if len(set(ids)) < 6 or len(set(ids)) != len(ids):
        raise SafetyStop("six distinct holdout IDs required")
    return sorted(ids, key=lambda case: (digest(("P2S-20261105" + case).encode()), case))[:6]


def select_validation(ids):
    if (
        len(ids) != 24
        or len(set(ids)) != 24
        or any(not isinstance(case, str) or not case.startswith("PSV") for case in ids)
    ):
        raise SafetyStop("V21 requires exactly 24 distinct fresh PSV IDs")
    return sorted(ids, key=lambda case: (digest(("P2S-V21-20261105" + case).encode()), case))[:6]


def read_ancestor(root, *, expected=None):
    """Read a completed direct parent without locks/writes or old response replay."""
    root = Path(root).resolve()
    paths = {
        name: root / name for name in ("experiment_config.json", "requests.json", "results.json")
    }
    if not all(path.is_file() for path in paths.values()):
        raise SafetyStop("ancestor journal/config/results missing")
    raw = {name: path.read_bytes() for name, path in paths.items()}
    hashes = {name: digest(value) for name, value in raw.items()}
    if expected and (str(root) != expected["root"] or hashes != expected["hashes"]):
        raise SafetyStop("ancestor artifact hash mutation; continuation forbidden")
    config, rows, result = (json.loads(raw[name]) for name in paths)
    if (
        config.get("schema") != "p2s-real-pairs-v1"
        or config.get("limits") != LIMITS
        or config.get("history_ancestor")
        or digest({k: v for k, v in config.items() if k != "config_sha256"})
        != config.get("config_sha256")
    ):
        raise SafetyStop("ancestor config hash/schema conflict or unsupported nested ancestry")
    if (
        not isinstance(rows, list)
        or not rows
        or not isinstance(result.get("probe"), dict)
        or not result["probe"].get("completion_valid")
    ):
        raise SafetyStop("ancestor requires completed requests and a successful probe")
    seen = set()
    sequences = {}
    complete_groups = {g["group"] for g in result.get("groups", [])}
    probe_rows = []
    for row in rows:
        if (
            not isinstance(row, dict)
            or row.get("schema") != "p2s-request-v1"
            or row.get("status") != "RESPONSE"
            or old.usage(row.get("usage")) is None
            or row.get("transport_error_type")
        ):
            raise SafetyStop("ancestor pending/unknown usage/corrupt request cannot be inherited")
        key = (row["group"], row["sequence"])
        if key in seen or type(row["sequence"]) is not int or row["sequence"] < 0:
            raise SafetyStop("ancestor duplicate request sequence conflict")
        seen.add(key)
        sequences.setdefault(row["group"], []).append(row["sequence"])
        parts = row["group"].rsplit(":", 2)
        if len(parts) != 3 or parts[1] not in config["snapshots"]:
            raise SafetyStop("ancestor group/source conflict")
        if (
            row.get("config_sha256") != config["config_sha256"]
            or row.get("source_sha256") != config["snapshots"][parts[1]]["source_sha256"]
        ):
            raise SafetyStop("ancestor request source/config hash conflict")
        if row["group"].startswith("__probe__:"):
            probe_rows.append(row)
        elif row["group"] not in complete_groups:
            raise SafetyStop("ancestor contains a request group without completed results")
    if any(values != list(range(len(values))) for values in sequences.values()):
        raise SafetyStop("ancestor request sequence is incomplete")
    if (
        len(probe_rows) != 1
        or probe_rows[0].get("http_status") != 200
        or probe_rows[0].get("model_error")
        or probe_rows[0]
        .get("response", {})
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
        != "P2S_OK"
    ):
        raise SafetyStop("ancestor probe response invalid")
    if expected and len(rows) != expected["row_count"]:
        raise SafetyStop("ancestor row count conflict")
    if any(digest(path.read_bytes()) != hashes[name] for name, path in paths.items()):
        raise SafetyStop("ancestor changed while reading")
    return config, rows, result


def inherit_budget(root, *, snapshots, roots, env_file, pricing):
    config, rows, result = read_ancestor(root)
    if (
        config.get("roots") != roots
        or config.get("env_file") != str(env_file.resolve())
        or config.get("pricing") != pricing
        or config.get("mode") != "M2"
        or config.get("provider_class") != "p2s.real_pairs.Provider"
    ):
        raise SafetyStop("ancestor source/provider/environment/pricing control conflict")
    for arm in ("R0", "R1"):
        before, after = config["snapshots"][arm], snapshots[arm]
        for key in (
            "provider_settings_sha256",
            "ambient_settings_sha256",
            "endpoint",
            "model",
            "caps",
            "signature_caps",
            "imports",
        ):
            if before.get(key) != after.get(key):
                raise SafetyStop(
                    "ancestor configured source/provider/environment fingerprint conflict"
                )
        if {p: h for p, h in before["files"].items() if p != "eval/answer_scoring.py"} != {
            p: h for p, h in after["files"].items() if p != "eval/answer_scoring.py"
        }:
            raise SafetyStop("ancestor application/shared source conflict")
    for path in (Q_HELPER, R5_HELPER, INSTRUMENTATION):
        if config["helper_hashes"].get(str(path.resolve())) != digest(path.read_bytes()):
            raise SafetyStop("ancestor frozen safety helper conflict")
    usage = [old.usage(row["usage"]) for row in rows]
    totals = dict(
        http_attempts=len(rows),
        accounted_tokens=sum(u["total_tokens"] for u in usage),
        estimated_usd=sum(
            u["prompt_tokens"] * pricing["input"] + u["completion_tokens"] * pricing["output"]
            for u in usage
        )
        / 1000000,
    )
    if any(
        totals[k] > LIMITS[b]
        for k, b in (
            ("http_attempts", "requests"),
            ("accounted_tokens", "tokens"),
            ("estimated_usd", "usd"),
        )
    ):
        raise SafetyStop("ancestor already exceeds global hard limits")
    root = Path(root).resolve()
    hashes = {
        name: digest((root / name).read_bytes())
        for name in ("experiment_config.json", "requests.json", "results.json")
    }
    history = dict(
        root=str(root),
        hashes=hashes,
        row_count=len(rows),
        totals=totals,
        seed_clock=config.get("seed_clock"),
        probe_group=next(row["group"] for row in rows if row["group"].startswith("__probe__:")),
    )
    # Re-read under the frozen manifest so configuration and ledger cannot come
    # from different parent revisions. Old dictionaries are never annotated.
    _, confirmed, _ = read_ancestor(root, expected=history)
    if confirmed != rows:
        raise SafetyStop("ancestor changed while freezing continuation")
    probe = dict(
        result["probe"], inherited_from=str(root), parent_results_sha256=hashes["results.json"]
    )
    return history, rows, probe


def verify_application_freeze(snapshots, freeze):
    # The candidate freeze intentionally records Python app source only. Full
    # snapshots additionally include skill JSON and other runtime contracts.
    candidate_python = {
        p: h
        for p, h in snapshots["R1"]["files"].items()
        if p.startswith("app/") and p.endswith(".py")
    }
    if candidate_python != freeze["app_hashes"]:
        raise SafetyStop("candidate frozen application hash conflict")
    non_python = [
        {
            p: h
            for p, h in snapshots[arm]["files"].items()
            if p.startswith("app/") and not p.endswith(".py")
        }
        for arm in ("R0", "R1")
    ]
    if non_python[0] != non_python[1]:
        raise SafetyStop("source pairs differ in non-Python app contracts/metadata")


def prepare(args):
    """Explicit future setup may fingerprint its supplied env; never sends HTTP."""
    run = args.run_dir.resolve()
    if any(p.name != ".lock" for p in run.iterdir()):
        raise SafetyStop("prepare cannot overwrite an existing experiment")
    parent_run = getattr(args, "budget_parent_run", None)
    explicit_freeze = getattr(args, "freeze_file", None)
    if (
        explicit_freeze
        and Path(explicit_freeze).resolve() != (HERE / "evidence/candidate_freeze.json").resolve()
        and not parent_run
    ):
        raise SafetyStop(
            "alternate freeze requires budget-parent-run; never reset the global budget"
        )
    roots = {"R0": args.r0_root.resolve(), "R1": args.r1_root.resolve()}
    snapshots = {v: worker_snapshot(p, args.env_file.resolve()) for v, p in roots.items()}
    freeze_file = Path(getattr(args, "freeze_file", None) or FREEZE).resolve()
    freeze = read(freeze_file)
    adapter = "v21" if parent_run else "v20"
    if parent_run and not getattr(args, "freeze_file", None):
        raise SafetyStop("V21 continuation requires an explicit new freeze file")
    if parent_run and Path(parent_run).resolve() == run:
        raise SafetyStop("ancestor cannot be the new run")
    if snapshots["R0"]["head"] != BASE:
        raise SafetyStop("baseline commit mismatch")
    verify_application_freeze(snapshots, freeze)
    if digest(SCORER.read_bytes()) != freeze["scorer_sha256"]:
        raise SafetyStop("frozen answer scorer conflict")
    for key in ("provider_settings_sha256", "ambient_settings_sha256", "endpoint", "model", "caps"):
        if snapshots["R0"][key] != snapshots["R1"][key]:
            raise SafetyStop("source pairs differ in common settings or output call-site caps")
    common_defaults = [
        {
            p: v
            for p, v in snapshots[arm]["signature_caps"].items()
            if p != "app/guardrails/hallucination.py"
        }
        for arm in ("R0", "R1")
    ]
    if common_defaults[0] != common_defaults[1]:
        raise SafetyStop(
            "common output cap signature defaults differ outside intentional Judge change"
        )
    shared = [
        p
        for p in snapshots["R0"]["files"]
        if p.startswith(("eval/", "knowledge/")) or p == "app/services/seed.py"
    ]
    if any(snapshots["R0"]["files"][p] != snapshots["R1"]["files"].get(p) for p in shared):
        raise SafetyStop("source pairs differ in shared evaluator/knowledge/seed")
    datasets = {"blind": args.blind_dataset.resolve()}
    answers = {"blind": args.blind_answers.resolve()}
    if adapter == "v20" or (
        getattr(args, "dev_dataset", None) and getattr(args, "dev_answers", None)
    ):
        datasets["development"], answers["development"] = (
            args.dev_dataset.resolve(),
            args.dev_answers.resolve(),
        )
    ids = {s: r5.dataset_ids(p) for s, p in datasets.items()}
    if adapter == "v20" and not set(DEV_IDS) <= set(ids["development"]):
        raise SafetyStop("predeclared development IDs absent")
    for path in [*datasets.values(), *answers.values()]:
        if freeze["datasets"].get(path.name) != digest(path.read_bytes()):
            raise SafetyStop("dataset/answer Gold differs from candidate freeze")
    if not args.pricing_url.startswith("https://") or not args.pricing_verified_date:
        raise SafetyStop("explicit verified pricing source/date required")
    pricing = {"input": args.input_price, "output": args.output_price}
    Ledger(run, pricing=pricing)
    history, inherited_rows, inherited_probe = None, [], None
    if parent_run:
        history, inherited_rows, inherited_probe = inherit_budget(
            parent_run,
            snapshots=snapshots,
            roots={v: str(p) for v, p in roots.items()},
            env_file=args.env_file,
            pricing=pricing,
        )
        selected = [dict(id=x, split="blind") for x in select_validation(ids["blind"])]
    else:
        selected = [dict(id=x, split="development") for x in DEV_IDS] + [
            dict(id=x, split="blind") for x in select_blind(ids["blind"])
        ]
    planned = [
        dict(case_id=case["id"], split=case["split"], variant=variant, rep=0)
        for index, case in enumerate(selected)
        for variant in (("R0", "R1") if index % 2 == 0 else ("R1", "R0"))
    ]
    ancestor_groups = {row["group"] for row in inherited_rows}
    if any(f"{g['case_id']}:{g['variant']}:{g['rep']}" in ancestor_groups for g in planned):
        raise SafetyStop("new plan conflicts with an ancestor paid group; never replay old cases")
    config = dict(
        schema="p2s-real-pairs-v2.1" if parent_run else "p2s-real-pairs-v1",
        score_adapter=adapter,
        score_scope="same-turn calls and tool-reason prefix; final case-wide environment oracle"
        if parent_run
        else "case-cumulative calls and tool status",
        freeze_file=str(freeze_file),
        history_ancestor=history,
        created_at=old.stamp(),
        roots={v: str(p) for v, p in roots.items()},
        snapshots=snapshots,
        helper_hashes=helper_hashes(freeze_file),
        candidate_app_source_commit=freeze["app_source_commit"],
        metadata_commit_policy="HEAD recorded at preparation; later metadata-only commits allowed only with identical frozen source bytes",
        datasets={
            s: dict(
                path=str(p),
                sha256=digest(p.read_bytes()),
                case_count=len(ids[s]),
                answers_path=str(answers[s]),
                answers_sha256=digest(answers[s].read_bytes()),
            )
            for s, p in datasets.items()
        },
        selected=selected,
        planned=planned,
        selection_rule="six fresh validation IDs by SHA256('P2S-V21-20261105'+ID), no paid development"
        if parent_run
        else "four predeclared development IDs; first six IDs by SHA256('P2S-20261105'+ID), no outcomes",
        mode="M2",
        database="fresh isolated SQLite memory per scenario",
        seed_clock=(history or {}).get("seed_clock") or old.stamp(),
        business_clock_controls=[
            "app.core.time.utcnow",
            "app.services.seed.utcnow",
            "app.repositories.models.utcnow",
            "app.repositories.session_repository.utcnow",
            "all callable ORM DateTime column defaults",
        ],
        provider_class="p2s.real_pairs.Provider",
        temperature=0,
        output_maximum=1024,
        per_group_http_limit=GROUP_LIMIT,
        http_attempts_per_generation=1,
        concurrency=1,
        repetitions=[0],
        limits=LIMITS,
        env_file=str(args.env_file.resolve()),
        pricing=pricing,
        pricing_url=args.pricing_url,
        pricing_verified_date=args.pricing_verified_date,
        prompt_differences={
            p: {v: snapshots[v]["prompts"].get(p) for v in roots}
            for p in sorted(set(snapshots["R0"]["prompts"]) | set(snapshots["R1"]["prompts"]))
            if snapshots["R0"]["prompts"].get(p) != snapshots["R1"]["prompts"].get(p)
        },
        judge_cap_defaults={v: snapshots[v]["signature_caps"] for v in roots},
        semantic_human_calibration="NOT_RUN",
        gold_to_agent=False,
    )
    config["config_sha256"] = digest(config)
    write(run / "experiment_config.json", config)
    write(run / "requests.json", inherited_rows)
    write(run / "results.json", dict(probe=inherited_probe, groups=[], status="PREPARED"))
    return dict(
        status="PREPARED",
        planned_groups=len(planned),
        paid_http_attempts=0,
        inherited_http_attempts=len(inherited_rows),
        inherited_budget=(history or {}).get("totals"),
        selected_ids=[case["id"] for case in selected],
        planned_order=[f"{group['case_id']}:{group['variant']}:0" for group in planned],
    )


def verify(run, env_file, variant):
    config = read(run / "experiment_config.json")
    if digest({k: v for k, v in config.items() if k != "config_sha256"}) != config["config_sha256"]:
        raise SafetyStop("config fingerprint hash conflict")
    if (
        config["schema"] not in {"p2s-real-pairs-v1", "p2s-real-pairs-v2.1"}
        or config["limits"] != LIMITS
        or config["per_group_http_limit"] != GROUP_LIMIT
        or config["concurrency"] != 1
        or config["mode"] != "M2"
        or config.get("freeze_file", str(FREEZE)) != str(FREEZE.resolve())
        or config["helper_hashes"] != helper_hashes(Path(config.get("freeze_file", FREEZE)))
        or str(env_file.resolve()) != config["env_file"]
        or str(SOURCE_ROOT) != config["roots"][variant]
    ):
        raise SafetyStop("harness/source/config fingerprint conflict")
    actual = fingerprint(env_file)
    frozen = config["snapshots"][variant]
    # Metadata checkpoints do not alter code: compare every source byte, import,
    # provider setting and cap, while preserving the preparation HEAD separately.
    r5.verify_fingerprint(
        {k: v for k, v in frozen.items() if k != "head"},
        {k: v for k, v in actual.items() if k != "head"},
    )
    for dataset in config["datasets"].values():
        for pathkey, hashkey in (("path", "sha256"), ("answers_path", "answers_sha256")):
            if digest(Path(dataset[pathkey]).read_bytes()) != dataset[hashkey]:
                raise SafetyStop("frozen dataset/answer hash conflict")
    return config, old.settings(str(env_file))


def score_captured(evidence, gold_rows, *, adapter="v20"):
    """Load current frozen scorer absolutely, only after Agent execution ends."""
    scorer = absolute_module("_p2s_frozen_answer_scoring", SCORER)
    trace, raw = evidence["traces"][0], evidence["results"][0]
    calls = raw["evidence"]["tool_calls"]
    tool_ok = not any(reason.startswith("turn:") for reason in raw["reasons"])
    env_metric = raw["metrics"].get("environment_state_correct")
    env_ok = bool(env_metric) if env_metric is not None else None
    if len(trace["turns"]) != len(gold_rows):
        raise SafetyStop("captured turn/answer annotation count mismatch")
    scores = []
    for turn, spec in zip(trace["turns"], gold_rows, strict=True):
        if adapter not in {"v20", "v21"}:
            raise SafetyStop("unknown score adapter")
        turn_tool_ok = (
            not any(reason.startswith(f"turn:{turn['turn']}:") for reason in raw["reasons"])
            if adapter == "v21"
            else tool_ok
        )
        state = turn.get("final_state", {})
        answer = (turn.get("response") or {}).get("answer", state.get("final_answer", ""))
        judged = next(
            (
                node.get("output", {}).get("extra", {}).get("faithfulness")
                for node in reversed(turn["nodes"])
                if node["node"] == "check_faithfulness"
            ),
            None,
        )
        scores.append(
            scorer.score_answer(
                answer=answer,
                gold=scorer.AnswerGold.model_validate(spec),
                calls=[
                    c
                    for c in calls
                    if (
                        c.get("turn", 0) == turn["turn"]
                        if adapter == "v21"
                        else c.get("turn", 0) <= turn["turn"]
                    )
                ],
                tool_success=turn_tool_ok,
                environment_success=env_ok,
                retrieved=state.get("retrieved_chunks") or [],
                judge_status=(judged or {}).get("status"),
            )
        )
    return scores


async def capture_case(case, dataset_hash, provider, *, allow_real_network, seed_clock):
    instrumented = absolute_module("_p2s_frozen_instrumentation", INSTRUMENTATION)
    original_state_value = instrumented.state_value

    def state_value(state):
        value = original_state_value(state)
        extra = state.get("extra") or {}
        selected = {
            k: extra[k]
            for k in (
                "faithfulness",
                "generation_error",
                "goal_coverage",
                "self_corrected",
                "generated_refusal",
            )
            if k in extra
        }
        if selected:
            value["extra"] = instrumented.safe_value(selected)
        return value

    # Frozen instrumentation is offline by default. Only this explicit paid worker
    # scope opens it; tests exercise the identical scope with MockTransport.
    with (
        patch.object(instrumented, "offline_network", nullcontext)
        if allow_real_network
        else nullcontext()
    ):
        with business_clock(seed_clock), patch.object(instrumented, "state_value", state_value):
            return await instrumented.evaluate_cases(
                [case],
                dataset_sha256=dataset_hash,
                mode="M2",
                provider="replay",
                llm_factory=lambda: provider,
            )


@contextmanager
def business_clock(seed_clock):
    """Freeze imported business aliases AND SQLAlchemy's captured default wrappers."""
    from sqlalchemy import DateTime

    from app.repositories.models import Base

    clock = datetime.fromisoformat(seed_clock)
    with ExitStack() as stack:
        for target in (
            "app.core.time.utcnow",
            "app.services.seed.utcnow",
            "app.repositories.models.utcnow",
            "app.repositories.session_repository.utcnow",
        ):
            stack.enter_context(patch(target, return_value=clock))
        for table in Base.metadata.tables.values():
            for column in table.columns:
                if (
                    isinstance(column.type, DateTime)
                    and column.default is not None
                    and column.default.is_callable
                ):
                    stack.enter_context(patch.object(column.default, "arg", lambda context: clock))
        yield


def next_group(config, result):
    done = {(g["case_id"], g["variant"], g["rep"]) for g in result["groups"]}
    return next(
        (g for g in config["planned"] if (g["case_id"], g["variant"], g["rep"]) not in done), None
    )


def summarize(result, ledger):
    return dict(
        status=result["status"],
        completed_groups=len(result["groups"]),
        requests=ledger.totals(),
        limits=ledger.limits,
        model_evaluation="REAL_PROVIDER_EXPERIMENT",
        semantic_human_calibration="NOT_RUN",
    )


async def execute(args):
    run = args.run_dir.resolve()
    config, settings = verify(run, args.env_file, args.variant)
    if not settings.llm_configured:
        raise SafetyStop("explicit env has no configured provider key")
    result = read(run / "results.json")
    ledger = Ledger(run, pricing=config["pricing"])
    ledger.check_pending()
    if args.command == "probe":
        if result["probe"] is not None:
            raise SafetyStop("probe already completed; never repeat")
        group = "__probe__:" + args.variant + ":0"
    else:
        if not result["probe"] or not result["probe"].get("completion_valid"):
            raise SafetyStop("one successful probe is required")
        if any(
            g["case_id"] == args.case_id and g["variant"] == args.variant and g["rep"] == args.rep
            for g in result["groups"]
        ):
            return dict(status="ALREADY_COMPLETED", **ledger.totals())
        expected = next_group(config, result)
        if expected is None or (args.case_id, args.variant, args.rep) != (
            expected["case_id"],
            expected["variant"],
            expected["rep"],
        ):
            raise SafetyStop("group differs from frozen alternating source/pilot order")
        group = f"{args.case_id}:{args.variant}:{args.rep}"
        if not any(row["group"] == group for row in ledger.rows):
            previous = [
                sum(
                    row["reserve_input"] + row["reserve_output"]
                    for row in ledger.rows
                    if row["group"] == name
                )
                for name in {
                    row["group"] for row in ledger.rows if not row["group"].startswith("__probe__:")
                }
            ]
            forecast_tokens = max([24000, *previous])
            ledger.forecast(
                GROUP_LIMIT,
                forecast_tokens,
                forecast_tokens * max(config["pricing"].values()) / 1000000,
            )
    provider = Provider(
        settings,
        ledger,
        group,
        source_sha256=config["snapshots"][args.variant]["source_sha256"],
        config_sha256=config["config_sha256"],
    )
    try:
        if args.command == "probe":
            response = await provider.generate(
                [dict(role="user", content="Reply exactly P2S_OK.")], max_tokens=32
            )
            value = dict(
                connected=True,
                completion_valid=response.content.strip() == "P2S_OK",
                model=response.model,
            )
            result["probe"] = value
        else:
            dataset = config["datasets"][expected["split"]]
            cases, dataset_hash = old.load_scenarios(Path(dataset["path"]))
            case = next(case for case in cases if case.id == args.case_id)
            evidence = await capture_case(
                case,
                dataset_hash,
                provider,
                allow_real_network=True,
                seed_clock=config["seed_clock"],
            )
            rows = [row for row in ledger.rows if row["group"] == group]
            transport = provider.client._transport
            if transport.sequence != len(rows):
                raise SafetyStop("replay ended before stored request sequence")
            # Durable actual public/node/tool/database capture precedes Gold loading
            # and answer scoring. A scoring crash can never lose paid responses.
            initial_seed_tables_sha256 = digest(evidence["traces"][0]["database_initial"]["tables"])
            live_rows = rows[-transport.live_attempts :] if transport.live_attempts else []
            live_usage = [old.usage(row.get("usage")) for row in live_rows]
            paid_tokens = sum(u["total_tokens"] for u in live_usage) if all(live_usage) else None
            reported_tokens_group = sum(
                (old.usage(row.get("usage")) or {}).get("total_tokens", 0) for row in rows
            )
            accounted_tokens_group = sum(
                u["total_tokens"]
                if (u := old.usage(row.get("usage")))
                else row["reserve_input"] + row["reserve_output"]
                for row in rows
            )
            captured = dict(
                evidence,
                model_evaluation="REAL_PROVIDER",
                real_model_evaluation="REAL_PROVIDER",
                provider=config["provider_class"],
                paid_api_calls=transport.live_attempts,
                paid_tokens=paid_tokens,
                reported_tokens_group=reported_tokens_group,
                accounted_tokens_group=accounted_tokens_group,
                unknown_usage_requests_group=sum(
                    old.usage(row.get("usage")) is None for row in rows
                ),
                evidence_origin="REAL_PROVIDER_COMPLETIONS"
                if transport.live_attempts
                else "COMPLETED_RESPONSE_REPLAY",
                initial_seed_tables_sha256=initial_seed_tables_sha256,
                raw_driver_metadata={
                    k: evidence[k]
                    for k in (
                        "model_evaluation",
                        "real_model_evaluation",
                        "provider",
                        "paid_api_calls",
                        "paid_tokens",
                    )
                },
            )
            write(run / "captures" / (group.replace(":", "_") + ".json"), captured)
            mate = next(
                (
                    g
                    for g in result["groups"]
                    if g["case_id"] == args.case_id and g["rep"] == args.rep
                ),
                None,
            )
            if mate and mate["initial_seed_tables_sha256"] != initial_seed_tables_sha256:
                raise SafetyStop(
                    "source-pair initial seed tables differ; capture saved, stop before further groups"
                )
            gold = read(Path(dataset["answers_path"]))[args.case_id]
            raw = evidence["results"][0]
            value = dict(
                case_id=args.case_id,
                variant=args.variant,
                rep=args.rep,
                split=expected["split"],
                group=group,
                status=raw["status"],
                raw_driver_result=raw,
                model_evaluation="REAL_PROVIDER",
                provider=config["provider_class"],
                source_sha256=config["snapshots"][args.variant]["source_sha256"],
                initial_seed_tables_sha256=initial_seed_tables_sha256,
                new_http_attempts=transport.live_attempts,
                http_attempts=len(rows),
                reported_tokens_group=reported_tokens_group,
                accounted_tokens_group=accounted_tokens_group,
                request_errors=[
                    {
                        k: row.get(k)
                        for k in ("sequence", "stage", "model_error", "transport_error_type")
                    }
                    for row in rows
                    if row.get("model_error") or row.get("transport_error_type")
                ],
                answer_scores=score_captured(
                    evidence, gold, adapter=config.get("score_adapter", "v20")
                ),
                score_scope=config.get("score_scope", "case-cumulative calls and tool status"),
                semantic_human_calibration="NOT_RUN",
            )
            result["groups"].append(value)
        verify(run, args.env_file, args.variant)
        result["status"] = "COMPLETED" if next_group(config, result) is None else "RUNNING"
        result["summary"] = summarize(result, ledger)
        write(run / "results.json", result)
        return dict(
            status="PROBE_COMPLETE" if args.command == "probe" else value["status"],
            group=group,
            **ledger.totals(),
        )
    finally:
        await provider.aclose()


def orchestrate(args):
    """Fresh source-bound workers; no credentials or HTTP in the coordinator."""
    run = args.run_dir.resolve()
    while True:
        with exclusive(run):
            config, result = read(run / "experiment_config.json"), read(run / "results.json")
            ledger = Ledger(run, pricing=config["pricing"])
            ledger.check_pending()
            group = next_group(config, result)
            if group is None or (
                args.command == "pilot" and group["case_id"] != config["selected"][0]["id"]
            ):
                return summarize(result, ledger)
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "run-group",
                "--run-dir",
                str(run),
                "--env-file",
                str(args.env_file.resolve()),
                "--source-root",
                config["roots"][group["variant"]],
                "--variant",
                group["variant"],
                "--case-id",
                group["case_id"],
                "--rep",
                str(group["rep"]),
            ]
        )
        if completed.returncode:
            raise SafetyStop(
                "worker stopped; preserve checkpoints and never resend uncertain requests"
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "prepare",
            "probe",
            "pilot",
            "run",
            "resume",
            "run-group",
            "summary",
            "_snapshot",
            "_imports",
        ],
    )
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--freeze-file", type=Path)
    parser.add_argument("--budget-parent-run", type=Path)
    parser.add_argument("--r0-root", type=Path)
    parser.add_argument("--r1-root", type=Path)
    parser.add_argument("--dev-dataset", type=Path)
    parser.add_argument("--blind-dataset", type=Path)
    parser.add_argument("--dev-answers", type=Path)
    parser.add_argument("--blind-answers", type=Path)
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
            value = (
                fingerprint(args.env_file) if args.command == "_snapshot" else r5.bound_imports()
            )
        elif args.command in {"pilot", "run", "resume"}:
            if args.run_dir is None:
                parser.error("--run-dir required")
            value = orchestrate(args)
        else:
            if args.run_dir is None:
                parser.error("--run-dir required")
            if args.command == "prepare":
                required = [
                    args.r0_root,
                    args.r1_root,
                    args.blind_dataset,
                    args.blind_answers,
                    args.input_price,
                    args.output_price,
                    args.pricing_url,
                    args.pricing_verified_date,
                ]
                if not args.budget_parent_run:
                    required.extend([args.dev_dataset, args.dev_answers])
                if any(v is None for v in required):
                    parser.error(
                        "prepare requires both roots, datasets, answer annotations and verified prices/date"
                    )
                args.run_dir.resolve().mkdir(parents=True, exist_ok=False)
            with exclusive(args.run_dir.resolve()):
                if args.command == "prepare":
                    value = prepare(args)
                elif args.command == "summary":
                    config = read(args.run_dir / "experiment_config.json")
                    value = summarize(
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
