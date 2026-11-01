"""Report verdict coverage separately from supported/unsupported judgments."""

from collections import Counter

from app.guardrails.hallucination import FaithfulnessResult, FaithfulnessStatus


def summarize_judgments(results: list[FaithfulnessResult]) -> dict:
    counts = Counter(r.status.value for r in results)
    valid = counts["SUPPORTED"] + counts["UNSUPPORTED"]
    n = len(results)
    return {
        "faithfulness": counts["SUPPORTED"] / valid if valid else None,
        "hallucination_rate": counts["UNSUPPORTED"] / valid if valid else None,
        "judged_coverage": valid / n if n else 0,
        "legacy_supported_fraction": counts["SUPPORTED"] / n if n else None,
        "status_counts": {s.value: counts[s.value] for s in FaithfulnessStatus},
    }
