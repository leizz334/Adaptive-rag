"""Read-only baseline, with no settings, model or database imports."""

import hashlib
import json
from pathlib import Path


def baseline_snapshot() -> dict:
    root = Path(__file__).resolve().parents[1]
    data = {}
    for path in sorted((root / "eval/dataset").glob("*.jsonl")):
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len({row["id"] for row in rows}) != len(rows):
            raise ValueError(f"Duplicate dataset ID: {path.name}")
        data[path.name] = {
            "rows": len(rows),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    files = ["eval/runner.py", "eval/metrics.py", "app/guardrails/hallucination.py"]
    return {
        "schema_version": "p1-baseline-v1",
        "datasets": data,
        "source_sha256": {f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in files},
        "legacy_limitations": [
            "tool_path_hit is answer heuristic, not tool accuracy",
            "no environment oracle",
            "judge errors mixed with unsupported",
        ],
        "model_evaluation": "NOT_RUN",
    }


if __name__ == "__main__":
    print(json.dumps(baseline_snapshot(), indent=2))
