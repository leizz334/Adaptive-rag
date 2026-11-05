"""Independent final-answer assertions; Gold is confined to this evaluator.

No Agent imports, tool execution or model calls. Open semantic coverage defaults
to NOT_ASSESSED. A closed annotated answer contract is narrower than arbitrary
natural-language truth; unsupported extra clauses remain unknown.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import Field, model_validator

from eval.contracts import Contract

_ENTITY = re.compile(r"(?:ORD\d+|SKU-[A-Za-z0-9_-]+)", re.I)
_NEGATIVE = re.compile(
    r"(?:并非|不是|不为|尚未|未|没有|不能确认|无法确认|不确定)[^，,。；;\n]{0,4}$"
)
_NEUTRAL = re.compile(r"[\s，,:：、（）()；;。.!！?？\-]*")
_MISSING = object()


class EvidenceRequirement(Contract):
    source: Literal["tool", "retrieval"] = "tool"
    tool: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    path: str
    expected: Any
    comparison: Literal["eq", "contains"] = "eq"


class FactAssertion(Contract):
    id: str
    goal: str
    subject: str = ""
    patterns: list[str] = Field(min_length=1)
    forbidden_patterns: list[str] = Field(default_factory=list)
    evidence_any_of: list[EvidenceRequirement] = Field(default_factory=list)


class AnswerGold(Contract):
    schema_version: Literal["answer-eval-v2.0"] = "answer-eval-v2.0"
    subgoals: list[str] = Field(min_length=1)
    facts: list[FactAssertion] = Field(default_factory=list)
    forbidden_patterns: list[str] = Field(default_factory=list)
    allowed_extra_patterns: list[str] = Field(default_factory=list)
    expected_abstention: bool = False
    semantic_required: bool = True

    @model_validator(mode="after")
    def valid_contract(self):
        if len(set(self.subgoals)) != len(self.subgoals) or len({f.id for f in self.facts}) != len(
            self.facts
        ):
            raise ValueError("Duplicate goal/fact IDs")
        if any(f.goal not in self.subgoals for f in self.facts):
            raise ValueError("Fact refers to missing subgoal")
        for pattern in (
            self.forbidden_patterns
            + self.allowed_extra_patterns
            + [p for f in self.facts for p in f.patterns + f.forbidden_patterns]
        ):
            re.compile(pattern)
        return self


def _path(value, path):
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part, _MISSING)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return _MISSING
    return value


def _observed(requirement, calls, retrieved):
    values = (
        retrieved
        if requirement.source == "retrieval"
        else [
            c.get("output", {})
            for c in calls
            if c.get("name") == requirement.tool
            and c.get("success") is True
            and not c.get("truncated")
            and c.get("status", "executed") in {"executed", "replayed"}
            and all(c.get("arguments", {}).get(k) == v for k, v in requirement.arguments.items())
        ]
    )
    for value in values:
        actual = _path(value, requirement.path)
        if actual is _MISSING:
            continue
        if (
            requirement.comparison == "eq"
            and type(actual) is type(requirement.expected)
            and actual == requirement.expected
        ):
            return True
        if (
            requirement.comparison == "contains"
            and isinstance(actual, str)
            and isinstance(requirement.expected, str)
            and requirement.expected in actual
        ):
            return True
    return False


def _positive_matches(pattern, text):
    return [
        m
        for m in re.finditer(pattern, text, re.I)
        if not _NEGATIVE.search(text[max(0, m.start() - 12) : m.start()])
    ]


def _fact_spans(fact, answer):
    subjects = {e.upper() for e in _ENTITY.findall(answer)}
    if fact.subject and fact.subject.upper() not in subjects:
        return []
    spans = []
    for pattern in fact.patterns:
        for match in _positive_matches(pattern, answer):
            earlier = list(_ENTITY.finditer(answer[: match.start()]))
            if not fact.subject or (
                earlier and earlier[-1].group().upper() == fact.subject.upper()
            ):
                spans.append((match.start(), match.end()))
    return spans


def _unknown_clauses(answer, gold):
    # Remove only annotated fact phrases, allowed presentation, and identifiers.
    # Unmatched natural language is not silently accepted as faithful.
    chars = list(answer)
    for fact in gold.facts:
        for start, end in _fact_spans(fact, answer):
            chars[start:end] = " " * (end - start)
    remainder = "".join(chars)
    for pattern in gold.allowed_extra_patterns:
        remainder = re.sub(pattern, "", remainder, flags=re.I)
    allowed_subjects = {f.subject.upper() for f in gold.facts if f.subject}
    remainder = _ENTITY.sub(
        lambda match: "" if match.group().upper() in allowed_subjects else match.group(), remainder
    )
    return [
        part.strip()
        for part in re.split(r"[。！？;；\n]", remainder)
        if part.strip() and not _NEUTRAL.fullmatch(part)
    ]


def score_answer(
    *,
    answer: str,
    gold: AnswerGold,
    calls: list[dict],
    tool_success: bool | None,
    environment_success: bool | None,
    retrieved: list[dict] | None = None,
    judge_status: str | None = None,
):
    """Evaluate a supplied final answer after execution; never runs the Agent."""
    retrieved = retrieved or []
    facts = []
    violations = [p for p in gold.forbidden_patterns if _positive_matches(p, answer)]
    for fact in gold.facts:
        matched = bool(_fact_spans(fact, answer))
        wrong = any(_positive_matches(p, answer) for p in fact.forbidden_patterns)
        evidence = (
            any(_observed(req, calls, retrieved) for req in fact.evidence_any_of)
            if fact.evidence_any_of
            else None
        )
        facts.append(
            dict(
                id=fact.id, goal=fact.goal, matched=matched, contradiction=wrong, evidence=evidence
            )
        )
    unknown_goals = [g for g in gold.subgoals if not any(f["goal"] == g for f in facts)]
    missing = [g for g in gold.subgoals if any(f["goal"] == g and not f["matched"] for f in facts)]
    completeness = sum(g not in missing and g not in unknown_goals for g in gold.subgoals) / len(
        gold.subgoals
    )
    unverified = _unknown_clauses(answer, gold)
    false_facts = bool(violations or any(f["contradiction"] for f in facts))
    unsupported = any(f["matched"] and f["evidence"] is False for f in facts)
    no_evidence = (
        any(f["matched"] and f["evidence"] is None for f in facts) and not gold.expected_abstention
    )
    correctness = (
        "FAIL"
        if false_facts
        else "NOT_ASSESSED"
        if unverified or unknown_goals or not facts
        else "PASS"
    )
    faithful = (
        "FAIL"
        if false_facts or unsupported
        else "NOT_ASSESSED"
        if no_evidence or unverified or gold.semantic_required
        else "PASS"
    )
    tool = "NOT_ASSESSED" if tool_success is None else "PASS" if tool_success else "FAIL"
    environment = (
        "NOT_ASSESSED" if environment_success is None else "PASS" if environment_success else "FAIL"
    )
    if "FAIL" in (tool, environment, correctness, faithful) or missing:
        overall = "FAIL"
    elif "NOT_ASSESSED" in (tool, environment, correctness, faithful) or unknown_goals:
        overall = "NOT_ASSESSED"
    else:
        overall = "PASS"
    abstention = (
        "PASS"
        if gold.expected_abstention
        and completeness == 1
        and not false_facts
        and not unsupported
        and not unverified
        and not unknown_goals
        else "FAIL"
        if gold.expected_abstention
        else "NOT_ASSESSED"
    )
    return dict(
        schema_version="answer-eval-v2.0",
        scope="DETERMINISTIC_ANNOTATED_FACTS_AND_CLAUSE_COVERAGE",
        TOOL_SUCCESS=tool,
        ENVIRONMENT_SUCCESS=environment,
        ANSWER_FACTUAL_CORRECTNESS=correctness,
        ANSWER_COMPLETENESS=completeness,
        ANSWER_FAITHFULNESS=faithful,
        ABSTENTION_CORRECTNESS=abstention,
        OVERALL_TASK_SUCCESS=overall,
        JUDGE_VALIDITY=judge_status or "DETERMINISTIC_NO_LLM_JUDGE",
        facts=facts,
        missing_subgoals=missing,
        unknown_subgoals=unknown_goals,
        unverified_clauses=unverified,
        forbidden_claims=violations,
        semantic_human_calibration="NOT_RUN",
    )
