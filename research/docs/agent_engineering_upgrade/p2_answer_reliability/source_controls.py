"""Recreate disclosed detached offline controls without touching frozen product source."""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PHASE = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def git(*args, cwd=ROOT):
    return subprocess.check_output(["git", *args], cwd=cwd).decode("utf-8")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build():
    evidence = PHASE / "evidence/s5_sources"
    evidence.mkdir(exist_ok=False)
    controls = {}
    for label, commit in (("S0", "e74f01d"), ("S1", "1c6b506"), ("S2", "e74f01d")):
        target = REPO / ".worktrees" / f"p2s-{label.lower()}"
        if target.exists():
            raise RuntimeError(f"Preserve existing control: {target}")
        git("worktree", "add", "--detach", str(target), commit)
        controls[label] = target
    s1, s2 = controls["S1"], controls["S2"]
    # Shared pure renderer is a dependency, including tool detail quoting. It
    # changes no tool routing, goals, provider, graph or successful execution.
    for target in (s1, s2):
        name = "app/agents/answer_evidence.py"
        write(target / name, (ROOT / name).read_text(encoding="utf-8"))
    name = "app/agents/nodes/faithfulness.py"
    text = (s1 / name).read_text(encoding="utf-8")
    text = text.replace(
        '        state.get("refused")\n',
        '        (state.get("refused") and not (state.get("extra") or {}).get("generated_refusal"))\n',
    )
    write(s1 / name, text)
    name = "app/agents/nodes/generate.py"
    text = (s1 / name).read_text(encoding="utf-8")
    text = text.replace(
        '"generation_error": generation_error}',
        '"generation_error": generation_error, "generated_refusal": payload.refused}',
    )
    assert '"generated_refusal": payload.refused' in text
    write(s1 / name, text)
    for name in (
        "app/agents/goals.py",
        "app/agents/nodes/planner.py",
        "app/retrieval/adaptive.py",
        "app/prompts/answer.py",
    ):
        write(s2 / name, (ROOT / name).read_text(encoding="utf-8"))
    # Derive from baseline, transplant only the goal dependencies/branches.
    baseline = (s2 / "app/agents/nodes/generate.py").read_text(encoding="utf-8")
    final = (ROOT / "app/agents/nodes/generate.py").read_text(encoding="utf-8")
    baseline = baseline.replace(
        "from app.agents.state import AgentState",
        "from app.agents.answer_evidence import safe_answer\nfrom app.agents.goals import coverage\nfrom app.agents.state import AgentState",
    )
    baseline = baseline.replace(
        "    if isinstance(llm, OfflineLLMProvider):\n",
        '    goal_query = state["user_query"] if strategy == RetrievalStrategy.AGENT else ""\n    if isinstance(llm, OfflineLLMProvider):\n'
        + final.split("    if isinstance(llm, OfflineLLMProvider):\n", 1)[1].split(
            "        answer, citation_ids = _offline_answer(state)", 1
        )[0],
        1,
    )
    # First occurrence above is inside the offline branch; select top-level block.
    goal_prompt = final[
        final.index(
            '    goals = coverage(goal_query, tools, "")\n',
            final.index("    selected = node_context"),
        ) : final.index('    preferences = state.get("memory_preferences")')
    ]
    baseline = baseline.replace(
        '    preferences = state.get("memory_preferences")',
        goal_prompt + '    preferences = state.get("memory_preferences")',
        1,
    )
    checked = final[
        final.index("        checked = coverage(") : final.index("        usage = response.usage")
    ]
    baseline = baseline.replace(
        "        usage = response.usage", checked + "        usage = response.usage", 1
    )
    baseline = baseline.replace(
        '        "token_usage": merged,\n',
        '        "token_usage": merged,\n        "extra": {**(state.get("extra") or {}), "goal_coverage": coverage(goal_query, tools, payload.answer)},\n',
        1,
    )
    write(s2 / "app/agents/nodes/generate.py", baseline)
    assert "LLMTruncationError" not in baseline
    assert 'answer=_extractive_fallback(state["user_query"], evidence, tool_text)' in baseline
    assert (
        baseline[baseline.index("def _extractive_fallback") :]
        == git("show", "e74f01d:app/agents/nodes/generate.py")[
            git("show", "e74f01d:app/agents/nodes/generate.py").index("def _extractive_fallback") :
        ]
    )
    controls["S3"] = ROOT
    manifest = {}
    for label, target in controls.items():
        hashes = {
            p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((target / "app").rglob("*.py"))
        }
        diff = git("diff", "--", "app", cwd=target)
        if label in {"S1", "S2"}:
            # git diff omits new dependencies, so record full exact content too.
            for name in ("app/agents/answer_evidence.py", "app/agents/goals.py"):
                path = target / name
                if (
                    path.exists()
                    and name
                    not in git("ls-tree", "-r", "--name-only", "HEAD", cwd=target).splitlines()
                ):
                    diff += "".join(
                        difflib.unified_diff(
                            [],
                            path.read_text(encoding="utf-8").splitlines(keepends=True),
                            fromfile="/dev/null",
                            tofile=name,
                        )
                    )
        write(evidence / f"{label}.patch", diff)
        manifest[label] = dict(
            source_root=str(target),
            head=git("rev-parse", "HEAD", cwd=target).strip(),
            app_hashes=hashes,
            patch_sha256=hashlib.sha256(diff.encode()).hexdigest(),
        )
    manifest["dependency_note"] = (
        "S1/S2 share frozen pure renderer with S3; S1 includes trusted-refusal patch only beyond reviewed answer fixes; S2 baseline exceptions/extractive/offline tail/Judge/provider preserved. Arms are mechanism bundles, not disjoint-file factorial effects."
    )
    write(evidence / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: str(v) for k, v in controls.items()}))


def correct_s1():
    """Repair initial control-only metadata omission; preserve the initial run."""
    target = REPO / ".worktrees/p2s-s1"
    name = "app/agents/nodes/generate.py"
    text = (target / name).read_text(encoding="utf-8")
    assert '"generated_refusal": payload.refused' not in text
    text = text.replace(
        '"generation_error": generation_error}',
        '"generation_error": generation_error, "generated_refusal": payload.refused}',
    )
    assert '"generated_refusal": payload.refused' in text
    imports = [
        node.module for node in ast.walk(ast.parse(text)) if isinstance(node, ast.ImportFrom)
    ]
    assert "app.agents.goals" not in imports
    write(target / name, text)
    evidence = PHASE / "evidence/s5_sources_correctedS1"
    evidence.mkdir(exist_ok=False)
    original = json.loads((PHASE / "evidence/s5_sources/manifest.json").read_bytes())
    original["S1"]["app_hashes"] = {
        p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((target / "app").rglob("*.py"))
    }
    diff = git("diff", "--", "app", cwd=target)
    write(evidence / "S1.patch", diff)
    original["S1"]["patch_sha256"] = hashlib.sha256(diff.encode()).hexdigest()
    original["correction"] = (
        "Initial S1 source-control generated_refusal replacement did not match compact source; original evidence/runs preserved, final corrected S1 rerun in S1_corrected. No candidate/scorer/data tuning."
    )
    write(evidence / "manifest.json", json.dumps(original, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    import sys

    correct_s1() if "--correct-s1" in sys.argv else build()
