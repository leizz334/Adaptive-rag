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


def paired_hallucination_drop(
    before: list[FaithfulnessResult], after: list[FaithfulnessResult]
) -> float | None:
    valid = {FaithfulnessStatus.SUPPORTED, FaithfulnessStatus.UNSUPPORTED}
    if len(before) != len(after) or [r.status in valid for r in before] != [
        r.status in valid for r in after
    ]:
        return None
    first = summarize_judgments(before)["hallucination_rate"]
    last = summarize_judgments(after)["hallucination_rate"]
    return (first - last) / first if first and last is not None else None
