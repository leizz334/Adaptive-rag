"""Run the public evaluation or recompute the checked-in evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
RELEASE = HERE / "release"
EVIDENCE = RELEASE / "evidence"
P0 = "38c4e2071cb9f9c8fc04ee9f834fe2635b88aea9"

# The historical manifests use the original paths. These are the only import
# lines changed in the archived runners when they were moved into eval.release.
FROZEN = {
    "artifacts/final/run_final.py": "agent/run_final.py",
    "artifacts/final/fixtures.json": "agent/fixtures.json",
    "artifacts/context_engineering/p6/run_p6.py": "memory/run_p6.py",
    "artifacts/context_engineering/p6/fixtures.json": "memory/fixtures.json",
    "artifacts/hybrid_planner/p5/run_p5.py": "shared/run_p5.py",
    "artifacts/hybrid_planner/p5/score_p5.py": "shared/score_p5.py",
    "artifacts/hybrid_planner/p3_5/budget.py": "shared/budget.py",
}
ORIGINAL_IMPORTS = {
    b"from eval.release.memory import run_p6 as context_replay": b"from artifacts.context_engineering.p6 import run_p6 as context_replay",
    b"from eval.release.shared import run_p5 as replay": b"from artifacts.hybrid_planner.p5 import run_p5 as replay",
    b"from eval.release.shared.score_p5 import ": b"from artifacts.hybrid_planner.p5.score_p5 import ",
    b"from eval.release.shared.budget import (": b"from artifacts.hybrid_planner.p3_5.budget import (",
}
ARCHIVED_HARNESSES = {
    "agent": {"b8ac095746afd380f94e15fe11ac7f247cb514b6"},
    "memory": {
        "a2189cc367bd9a3da8666939a0bf4c411f7dbaed",
        "1a806630fd53babad260adef6b304ac1362993b2",
    },
}
REPLAY_CONTRACT_IMPORTS = (
    b"from eval.environment import BusinessEnvironment\n"
    b"from eval.multiturn import load_scenarios\n"
)
REPLAY_SCORER_IMPORT = (
    b"from artifacts.hybrid_planner.p5.score_p5 import metric_group, score_case\n"
)
RAG_COSTS = {
    "pipeline_usd_at_list_price",
    "evaluation_usd_at_list_price",
    "total_usd_at_list_price",
}


def activate_release() -> None:
    if not __package__:
        # Launching this file from a detached baseline checkout keeps that
        # checkout's application and eval contracts first on the import path.
        sys.path.insert(0, str(Path.cwd()))
        import eval as eval_package

        eval_package.__path__.append(str(HERE))


def frozen_hashes(suite: str) -> dict[str, str]:
    hashes = {}
    excluded = (
        {"memory/fixtures.json"}
        if suite == "agent"
        else {"agent/fixtures.json", "agent/run_final.py"}
    )
    for original, local in FROZEN.items():
        if local in excluded:
            continue
        content = (RELEASE / local).read_bytes().replace(b"\r\n", b"\n")
        for present, previous in ORIGINAL_IMPORTS.items():
            content = content.replace(present, previous)
        if local == "shared/run_p5.py":
            content = content.replace(REPLAY_CONTRACT_IMPORTS, b"").replace(
                REPLAY_SCORER_IMPORT, REPLAY_SCORER_IMPORT + REPLAY_CONTRACT_IMPORTS
            )
        hashes[original] = hashlib.sha256(content).hexdigest()
    return hashes


def git_head(directory: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--verify", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def run_agent(args: argparse.Namespace) -> None:
    from eval.release.agent import run_final as agent
    from eval.release.shared import run_p5 as replay

    if args.verify:
        directories = (
            [args.output]
            if args.output
            else [
                EVIDENCE / "agent" / "main",
                EVIDENCE / "agent" / "react",
            ]
        )
        for directory in directories:
            invoke_archived(agent, "agent", directory)
        return

    output = args.output
    if output is None:
        raise SystemExit("--output is required for a new run or collection")
    command = ["--output", str(output)]
    for flag, value in (
        ("--block", args.block),
        ("--cap-cny", args.cap_cny),
        ("--max-requests", args.max_requests),
    ):
        if value is not None:
            command.extend((flag, str(value)))
    if args.collect:
        invoke(agent, [*command, "--collect"])
        return
    command.extend(("--arm", args.arm))
    if args.dry_run:
        command.append("--dry-run")
    if args.offline:
        if args.arm != "E" or args.source_commit:
            raise SystemExit("Use --arm E for the offline release evaluation")

        # This manifest records actual working files and also works from a
        # source distribution with no Git executable or object database.
        def offline_manifest(options, cases, oracles, digest):
            from eval.release.shared.budget import HOST, MODEL

            source = Path.cwd().resolve()
            if source != HERE.parent:
                raise replay.RunStopped("Run the offline evaluation from the release root")
            paths = list(source.glob("app/**/*.py")) + list(source.glob("knowledge/**/*.md"))
            return {
                "arm": options.arm,
                "fixtures_sha256": digest,
                "evaluation_inputs": frozen_hashes("agent"),
                "source_files": {
                    path.relative_to(source).as_posix(): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in sorted(paths)
                },
                "seed_time": replay.CLOCK.isoformat(),
                "configured_live_provider": f"https://{HOST}",
                "configured_live_model": MODEL,
            }

        with patch.object(agent, "_release_p5", offline_manifest):
            invoke(agent, [*command, "--offline"])
        return

    source_commit = git_head(Path.cwd())
    harness_commit = git_head(HERE.parent)
    if args.source_commit and args.source_commit != source_commit:
        raise SystemExit("--source-commit must match the selected checkout's full HEAD")
    if args.arm == "A" and source_commit != P0:
        raise SystemExit(f"Arm A requires the public P0 source checkout at {P0}")
    if args.arm not in {"A", "R0"} and Path.cwd().resolve() != HERE.parent:
        raise SystemExit("Run the release arm from the release checkout")
    dirty = subprocess.check_output(
        [
            "git",
            "-C",
            str(HERE.parent),
            "status",
            "--porcelain",
            "--",
            "eval/reproduce.py",
            "eval/release",
        ],
        text=True,
    )
    if dirty:
        raise SystemExit("Commit the release harness before running a live arm")

    def validate_commit(commit: str) -> None:
        # The two commits may live in separate checkouts with separate histories.
        if commit not in (source_commit, harness_commit):
            raise replay.RunStopped("The checked out source and harness commits are required")

    with (
        patch.object(replay, "check_commit", validate_commit),
        patch.object(agent, "verify_harness", lambda _: frozen_hashes("agent")),
    ):
        invoke(
            agent,
            [
                *command,
                "--source-commit",
                source_commit,
                "--harness-commit",
                harness_commit,
            ],
        )


def invoke(driver, arguments: list[str]) -> None:
    with patch.object(sys, "argv", [sys.argv[0], *arguments]):
        driver.main()


def invoke_archived(driver, suite: str, directory: Path) -> None:
    from eval.release.shared.budget import RunStopped

    def check_frozen_harness(commit: str) -> dict[str, str]:
        if commit not in ARCHIVED_HARNESSES[suite]:
            # A new run can be verified with the clean release checkout where
            # it was made. Historical releases use the archived input hashes.
            if suite != "agent" or commit != git_head(HERE.parent):
                raise RunStopped(f"Unexpected {suite} harness commit {commit}")
        return frozen_hashes(suite)

    with patch.object(driver, "verify_harness", check_frozen_harness):
        invoke(driver, ["--verify", "--output", str(directory)])


def verify_rag() -> None:
    from eval.rerank_ablation import GROUPS, ranking_metrics, summarize
    from eval.runner import RAG_PATH, _keyword_hit, load_jsonl

    gold_hash = hashlib.sha256(RAG_PATH.read_bytes()).hexdigest()
    gold_cases = {row["id"]: row for row in load_jsonl(RAG_PATH)}
    for setting in ("natural", "forced"):
        folder = EVIDENCE / "rag" / setting
        manifest = json.loads((folder / "manifest.json").read_bytes())
        expected_ids = set(manifest["case_ids"])
        if manifest["gold_sha256"] != gold_hash:
            raise SystemExit(f"RAG {setting}: gold data differs from the recorded run")
        for group in GROUPS:
            rows = [
                json.loads(line) for line in (folder / f"{group}.jsonl").read_bytes().splitlines()
            ]
            if {row["id"] for row in rows} != expected_ids or len(rows) != len(expected_ids):
                raise SystemExit(f"RAG {setting}/{group}: case set differs from manifest")
            for row in rows:
                case = gold_cases[row["id"]]
                gold = set(case["relevant_doc_ids"])
                docs = {chunk["id"]: chunk["doc"] for chunk in row["ranked"]}
                context = {docs[identifier] for identifier in row["context_ids"]}
                if (
                    row["group"] != group
                    or row["query"] != case["query"]
                    or row["gold_doc_ids"] != sorted(gold)
                    or row["ranking"] != ranking_metrics(gold, list(dict.fromkeys(docs.values())))
                    or row["context_gold_doc_recall"] != len(context & gold) / len(gold)
                    or row["all_gold_docs_in_context"] != (gold <= context)
                    or row["keyword_hit"]
                    != _keyword_hit(row["answer"], case["gold_answer_contains"])
                ):
                    raise SystemExit(f"RAG {setting}/{group}: case metrics differ for {row['id']}")
            recomputed = {
                cohort: summarize(
                    [row for row in rows if cohort == "all" or row["cohort"] == cohort]
                )
                for cohort in ("all", "single", "multi")
            }
            recorded = json.loads((folder / f"{group}-summary.json").read_bytes())
            # The source runs used a different Python version. Float summation
            # can vary below the precision of the published USD costs.
            for cohort, metrics in recomputed.items():
                for name in RAG_COSTS & metrics.keys():
                    actual, expected = metrics[name], recorded[cohort][name]
                    if (
                        actual is not None
                        and expected is not None
                        and math.isclose(actual, expected, rel_tol=0, abs_tol=1e-12)
                    ):
                        metrics[name] = expected
            if recorded != recomputed:
                raise SystemExit(f"RAG {setting}/{group}: recomputed metrics differ")
        print(
            json.dumps(
                {
                    "suite": "rag",
                    "setting": setting,
                    "groups": len(GROUPS),
                    "cases_per_group": len(expected_ids),
                    "verified": True,
                }
            )
        )


def main() -> None:
    activate_release()
    parser = argparse.ArgumentParser(description=__doc__)
    suites = parser.add_subparsers(dest="suite", required=True)
    agent = suites.add_parser("agent", help="Verify or run the frozen Agent evaluation")
    mode = agent.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--arm", choices=("A", "E", "R0", "R1", "R2"))
    mode.add_argument("--collect", action="store_true")
    agent.add_argument("--output", type=Path)
    agent.add_argument("--source-commit")
    agent.add_argument("--block", type=int, choices=(0, 1))
    agent.add_argument("--cap-cny")
    agent.add_argument("--max-requests", type=int)
    agent.add_argument("--offline", action="store_true")
    agent.add_argument("--dry-run", action="store_true")
    for name in ("memory", "skills", "rag"):
        suites.add_parser(name).add_argument("--verify", action="store_true", required=True)
    args = parser.parse_args()
    if args.suite == "agent":
        if (
            args.offline or args.dry_run or args.block is not None or args.source_commit
        ) and not args.arm:
            agent.error("These options require --arm")
        run_agent(args)
    elif args.suite == "memory":
        from eval.release.memory import run_p6 as memory

        for batch in ("main", "retest"):
            invoke_archived(memory, "memory", EVIDENCE / "memory" / batch)
    elif args.suite == "skills":
        from eval.release import skills

        skills.verify(EVIDENCE / "skills")
    else:
        verify_rag()


if __name__ == "__main__":
    main()
