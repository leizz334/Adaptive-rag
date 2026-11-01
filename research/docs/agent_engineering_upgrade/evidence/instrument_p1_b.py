"""One-time P1-B source edit, AST-located decorators; idempotent."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TARGETS = {
    "app/agents/nodes/guardrail.py": {"guardrail_node": ("node.guardrail", "chain")},
    "app/agents/nodes/router.py": {
        "router_node": ("node.router", "chain"),
        "intent_node": ("node.intent", "chain"),
    },
    "app/agents/nodes/retrieval.py": {"retrieval_node": ("node.retrieval", "chain")},
    "app/agents/nodes/planner.py": {"planner_node": ("node.planner", "chain")},
    "app/agents/nodes/executor.py": {"executor_node": ("node.executor", "chain")},
    "app/agents/nodes/generate.py": {
        "generate_node": ("node.generate", "chain"),
        "refuse_node": ("node.refuse", "chain"),
    },
    "app/agents/nodes/faithfulness.py": {
        "faithfulness_node": ("node.faithfulness", "chain"),
        "self_correct_answer": ("answer.self_correct", "chain"),
    },
    "app/agents/nodes/memory.py": {"memory_node": ("node.memory", "chain")},
    "app/providers/deepseek.py": {
        "generate": ("llm.deepseek", "llm"),
        "_call": ("llm.http_attempt", "chain"),
    },
    "app/retrieval/hybrid.py": {"retrieve": ("retrieval.hybrid", "retriever")},
    "app/retrieval/bm25.py": {"search": ("retrieval.bm25", "retriever")},
    "app/retrieval/vector.py": {"search": ("retrieval.vector", "retriever")},
    "app/retrieval/reranker.py": {"rerank": ("retrieval.rerank", "retriever")},
    "app/retrieval/query_rewrite.py": {"rewrite": ("query.rewrite", "chain")},
    "app/retrieval/self_rag.py": {"_grade": ("evidence.grade", "chain")},
    "app/memory/summarizer.py": {"summarize": ("memory.summary", "chain")},
    "app/tools/base.py": {"run": ("tool.execute", "tool")},
}

if __name__ == "__main__":
    for relative, targets in TARGETS.items():
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        if "from app.observability.tracing import traced" in text:
            continue
        tree = ast.parse(text)
        lines = text.splitlines()
        inserts = []
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in targets:
                name, kind = targets[node.name]
                found.add(node.name)
                inserts.append(
                    (node.lineno - 1, " " * node.col_offset + f'@traced("{name}", "{kind}")')
                )
        assert found == set(targets), (relative, found)
        first_import = next(
            n
            for n in tree.body
            if isinstance(n, ast.Import | ast.ImportFrom)
            and not (isinstance(n, ast.ImportFrom) and n.module == "__future__")
        )
        inserts.append((first_import.lineno - 1, "from app.observability.tracing import traced"))
        for at, value in sorted(inserts, reverse=True):
            lines.insert(at, value)
        updated = "\n".join(lines) + "\n"
        ast.parse(updated)
        path.write_bytes(updated.encode("utf-8"))
        print(relative)
