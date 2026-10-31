"""Offline P0-A evidence validation; no app imports, DB/model/network operations.

Run from any directory with Conda adaptive-rag Python and -B. The only files
written are the two JSON evidence files next to this script, using atomic replace.
PASS describes source/document checks, never business or model test execution.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


HERE = Path(__file__).resolve().parent
STATE = HERE.parent
ROOT = HERE.parents[3]
PREFIX = "research/docs/agent_engineering_upgrade/"
REPORT = STATE / "audits/architecture.md"


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def atomic_json(path: Path, payload: dict) -> None:
    assert path.parent == HERE, "Evidence writes must stay in the audit evidence directory"
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(payload, output, ensure_ascii=False, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def tree(relative: str) -> ast.Module:
    return ast.parse((ROOT / relative).read_text(encoding="utf-8-sig"))


def function(relative: str, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    return next(
        node
        for node in ast.walk(tree(relative))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )


def attr_calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [
        item for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and item.func.attr == name
    ]


def validate() -> dict:
    assert ROOT == Path(git("rev-parse", "--show-toplevel")).resolve()
    assert Path(sys.executable).resolve().parent.name.lower() == "adaptive-rag"
    state = json.loads((STATE / "feature-list.json").read_text(encoding="utf-8"))
    baseline = json.loads((HERE / "initial-workspace.json").read_text(encoding="utf-8"))
    assert state["phase"] == "P0"
    assert [task["task_id"] for task in state["tasks"]] == ["P0-" + x for x in "ABCDEFG"]
    required = {
        "task_id", "description", "dependencies", "status", "passes",
        "acceptance_criteria", "evidence_files", "validation_results", "commit_hash", "next_action",
    }
    for task in state["tasks"]:
        assert required <= task.keys()
        assert type(task["passes"]) is bool
    assert all(task["status"] == "pending" and not task["passes"] for task in state["tasks"][1:])
    assert state["initializer"]["commit_hash"]
    git("cat-file", "-e", state["initializer"]["commit_hash"] + "^{commit}")

    checks: list[dict] = []

    def passed(name: str, detail: object) -> None:
        checks.append({"check": name, "result": "PASS", "basis": "SOURCE_VERIFIED", "detail": detail})

    passed("state_schema_and_single_task_scope", "P0-A only; P0-B..P0-G remain pending/false")
    changed: list[str] = []
    for group in ("tracked_sha256", "preexisting_untracked_sha256"):
        for relative, expected in baseline[group].items():
            path = ROOT / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                changed.append(relative)
    assert not changed, {"baseline_files_changed": changed}
    outside_untracked = {
        path for path in git("ls-files", "--others", "--exclude-standard").splitlines()
        if path and not path.startswith(PREFIX)
    }
    assert outside_untracked == set(baseline["preexisting_untracked_sha256"])
    outside_tracked_changes = [
        path for path in git("diff", baseline["git_head"], "--name-only").splitlines()
        if path and not path.startswith(PREFIX)
    ]
    assert not outside_tracked_changes, outside_tracked_changes
    passed("outside_scope_integrity", {
        "tracked_files": len(baseline["tracked_sha256"]),
        "preexisting_untracked_files": len(baseline["preexisting_untracked_sha256"]),
        "modified_or_missing": changed,
        "new_untracked_outside_scope": [],
    })

    graph = tree("app/agents/graph.py")
    node_names = [ast.literal_eval(call.args[0]) for call in attr_calls(graph, "add_node")]
    expected_nodes = {
        "apply_guardrail", "classify_intent", "route_complexity", "retrieve_docs",
        "plan_tasks", "execute_tools", "generate_answer", "refuse_answer",
        "check_faithfulness", "compact_memory",
    }
    assert set(node_names) == expected_nodes and len(node_names) == 10
    edges = sorted((ast.unparse(call.args[0]), ast.unparse(call.args[1])) for call in attr_calls(graph, "add_edge"))
    expected_edges = sorted([
        ("START", "'apply_guardrail'"),
        ("'classify_intent'", "'route_complexity'"),
        ("'retrieve_docs'", "'generate_answer'"),
        ("'plan_tasks'", "'execute_tools'"),
        ("'execute_tools'", "'generate_answer'"),
        ("'generate_answer'", "'check_faithfulness'"),
        ("'refuse_answer'", "'compact_memory'"),
        ("'check_faithfulness'", "'compact_memory'"),
        ("'compact_memory'", "END"),
    ])
    assert edges == expected_edges
    conditional = sorted(ast.literal_eval(call.args[0]) for call in attr_calls(graph, "add_conditional_edges"))
    assert conditional == ["apply_guardrail", "route_complexity"]
    assert not attr_calls(graph, "compile")[0].keywords
    route = function("app/agents/graph.py", "_route_after_complexity")
    mapping = next(node.value for node in route.body if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict))
    destinations = {key.attr: ast.literal_eval(value) for key, value in zip(mapping.keys, mapping.values)}
    assert destinations == {
        "DIRECT": "generate_answer", "REFUSE": "refuse_answer", "SINGLE": "retrieve_docs",
        "MULTI": "retrieve_docs", "AGENT": "plan_tasks",
    }
    passed("graph_nodes_edges_and_routing", {"nodes": sorted(node_names), "edges": edges, "routes": destinations})

    generate = function("app/agents/nodes/generate.py", "generate_node")
    reads = {
        node.slice.value
        for node in ast.walk(generate)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
        and node.value.id == "state" and isinstance(node.slice, ast.Constant)
    }
    reads.update(
        call.args[0].value for call in attr_calls(generate, "get")
        if isinstance(call.func.value, ast.Name) and call.func.value.id == "state"
        and call.args and isinstance(call.args[0], ast.Constant)
    )
    assert not {"messages", "summary"} & reads
    initial = function("app/services/chat_service.py", "_initial_state")
    result = next(node.value for node in initial.body if isinstance(node, ast.Return))
    initial_fields = {ast.literal_eval(key): value for key, value in zip(result.keys, result.values)}
    assert ast.literal_eval(initial_fields["summary"]) == ""
    passed("state_and_generation_context_boundaries", {"generate_state_reads": sorted(reads), "initial_summary": ""})

    provider = function("app/providers/deepseek.py", "generate")
    strings = {node.value for node in ast.walk(provider) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert "tools" not in strings and "tool_calls" not in strings
    assert "/chat/completions" in strings
    function("app/tools/base.py", "run")
    function("app/agents/nodes/planner.py", "_sanitize_plan")
    passed("provider_and_tool_calling_boundary", "Custom HTTP completion + AgentPlan JSON + Tool.run dispatch; no native tool_calls payload")

    stream = function("app/services/chat_service.py", "stream")
    assert attr_calls(stream, "astream")
    assert not any(ast.unparse(call.func) == "self._llm.stream" for call in attr_calls(stream, "stream"))
    commits = [call.lineno for call in attr_calls(stream, "commit")]
    token_lines = [
        node.lineno for node in ast.walk(stream)
        if isinstance(node, ast.Yield) and isinstance(node.value, ast.Dict)
        and any(isinstance(value, ast.Constant) and value.value == "token" for value in node.value.values)
    ]
    assert commits and token_lines and max(commits) < min(token_lines)
    assert attr_calls(stream, "create_task") and attr_calls(stream, "cancel")
    passed("sse_static_lifecycle", {"commit_lines": commits, "token_yield_lines": token_lines, "note": "No runtime ASGI/disconnect claim"})

    text = REPORT.read_text(encoding="utf-8")
    assert len(re.findall(r"^```", text, re.MULTILINE)) % 2 == 0
    references: dict[str, dict] = {}
    local_links: list[tuple[Path, str]] = []
    expected_outputs = {HERE / "P0-A-source-index.json", HERE / "P0-A-validation.json"}
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        assert not target.startswith(("http://", "https://")), "P0-A does not depend on remote evidence"
        path_text, _, anchor = target.partition("#")
        path = (REPORT.parent / path_text).resolve()
        assert path.is_relative_to(ROOT)
        assert path.is_file() or path in expected_outputs, target
        local_links.append((path, target))
        if path.is_relative_to(STATE):
            continue
        relative = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        entry = references.setdefault(relative, {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "line_count": len(lines), "anchors": [], "evidence_label": "SOURCE_VERIFIED",
        })
        if anchor:
            assert re.fullmatch(r"L[1-9][0-9]*", anchor), target
            line = int(anchor[1:])
            assert 1 <= line <= len(lines), target
            if line not in {item["line"] for item in entry["anchors"]}:
                entry["anchors"].append({"line": line, "text": lines[line - 1].strip()})
        if path.suffix == ".py" and "symbols" not in entry:
            parsed = ast.parse(path.read_text(encoding="utf-8-sig"))
            entry["symbols"] = [
                {"name": node.name, "line": node.lineno, "end_line": node.end_lineno}
                for node in ast.walk(parsed)
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            ]
    passed("report_references_syntax_and_source_index", {"local_link_occurrences": len(local_links), "source_files": len(references)})
    assert "仅阅读测试代码，未运行" in text and "TEST_VERIFIED" in text
    assert len(state["tasks"][0]["acceptance_criteria"]) == 6
    passed("evidence_labels_and_acceptance_scope", "Six P0-A acceptance items covered; no business test success claims; P0-B..P0-G not executed")

    index = {
        "task_id": "P0-A", "source_baseline_git_head": baseline["git_head"],
        "evidence_label": "SOURCE_VERIFIED", "files": references,
        "note": "Source/test/doc positions and fingerprints; tests were not executed. Repository documentation claims remain DOCUMENTED_ONLY in the report.",
    }
    atomic_json(HERE / "P0-A-source-index.json", index)
    output = {
        "task_id": "P0-A", "validation_kind": "offline_static_validation",
        "result": "PASS", "python_executable": sys.executable,
        "python_version": sys.version.split()[0], "source_baseline_git_head": baseline["git_head"],
        "git_head_at_validation": git("rev-parse", "HEAD"), "checks": checks,
        "acceptance_results": [
            {"criterion": item, "result": "PASS", "validation_scope": "source/document/static checks only"}
            for item in state["tasks"][0]["acceptance_criteria"]
        ],
        "business_tests_run": False, "application_imported_or_started": False,
        "paid_llm_calls": 0, "model_downloads_or_training": 0,
        "database_operations": 0, "trace_uploads": 0,
        "not_run": [
            {"item": "pytest / TestClient", "label": "BLOCKED", "reason": "Repository conftest creates data/local and HTTP lifespan can create schema/ingest; no business-directory writes authorized."},
            {"item": "Service/DB/model/remote dependencies", "label": "BLOCKED", "reason": "P0 side-effect restrictions; only source evidence is claimed."},
            {"item": "Concurrency, SSE cancellation and recovery", "label": "HYPOTHESIS", "reason": "Structural behavior inspected; no runtime fault injection executed."},
        ],
    }
    atomic_json(HERE / "P0-A-validation.json", output)
    assert all(path.is_file() for path, _ in local_links)
    return output


if __name__ == "__main__":
    result = validate()
    print(json.dumps({
        "task_id": result["task_id"], "result": result["result"],
        "checks": len(result["checks"]), "acceptance_items": len(result["acceptance_results"]),
        "business_tests_run": result["business_tests_run"],
        "python_executable": result["python_executable"],
    }, ensure_ascii=False, indent=2))
