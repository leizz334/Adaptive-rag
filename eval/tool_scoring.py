"""Deterministic tool metrics from execution evidence, never answer text."""

from collections import Counter
from decimal import Decimal, InvalidOperation

from eval.contracts import ToolCall, TrajectorySpec


def _matches(actual: dict, expected: dict) -> bool:
    for key, want in expected.items():
        if key not in actual:
            return False
        got = actual[key]
        if type(want) in (int, float) and type(got) in (int, float, str):
            try:
                if Decimal(str(got)) != Decimal(str(want)):
                    return False
            except InvalidOperation:
                return False
        elif type(got) is not type(want) or got != want:
            return False
    return True


def score_tools(calls: list[ToolCall], spec: TrajectorySpec) -> dict:
    active = [c for c in calls if c.status != "denied"]
    names = [c.name for c in active]
    counts = Counter(names)
    required = Counter(e.name for e in spec.required)
    allowed = set(spec.allowed) | set(required) | {n for path in spec.valid_paths for n in path}
    missing = sum(max(0, n - counts[name]) for name, n in required.items())
    selected = sum(min(counts[name], n) for name, n in required.items())
    selection = (
        selected / sum(required.values()) if required else float(all(n in allowed for n in names))
    )
    relevant = [c for c in active if c.name in required]
    correct_args = sum(
        any(e.name == c.name and _matches(c.arguments, e.arguments) for e in spec.required)
        for c in relevant
    )
    argument_accuracy = correct_args / (len(relevant) + missing) if relevant or missing else None
    # Maximum one-to-one matching: repeating order A cannot satisfy required B.
    assigned: dict[int, int] = {}

    def match(index, seen):
        expected = spec.required[index]
        for j, call in enumerate(relevant):
            if (
                j in seen
                or call.name != expected.name
                or not _matches(call.arguments, expected.arguments)
            ):
                continue
            seen.add(j)
            if j not in assigned or match(assigned[j], seen):
                assigned[j] = index
                return True
        return False

    if spec.required:
        covered = sum(match(i, set()) for i in range(len(spec.required))) / len(spec.required)
        argument_accuracy = min(argument_accuracy or 0, covered)
    unnecessary = sum(n for name, n in counts.items() if name not in allowed)
    unnecessary += sum(
        max(0, count - spec.max_calls.get(name, max(1, required[name])))
        for name, count in counts.items()
        if name in allowed
    )
    order_ok = all(
        a in names
        and b in names
        and max(i for i, n in enumerate(names) if n == a)
        < min(i for i, n in enumerate(names) if n == b)
        for a, b in spec.before
    )
    path_ok = not spec.valid_paths or names in spec.valid_paths
    executed = [c for c in calls if c.status == "executed"]
    failures = Counter(c.failure_kind or "tool_result_failure" for c in calls if not c.success)
    return {
        "tool_selection_accuracy": selection,
        "tool_argument_accuracy": argument_accuracy,
        "trajectory_valid": int(not missing and not unnecessary and order_ok and path_ok),
        "unnecessary_tool_calls": unnecessary,
        "tool_execution_success": sum(c.success for c in executed) / len(executed)
        if executed
        else None,
        "failure_counts": dict(failures),
        "idempotent_replays": sum(c.status == "replayed" for c in calls),
        "denied_calls": sum(c.status == "denied" for c in calls),
        "missing_required_calls": missing,
    }
