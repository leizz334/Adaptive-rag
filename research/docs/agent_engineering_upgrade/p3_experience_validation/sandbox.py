"""Research-only selection and selective prompt injection; no production imports."""

from app.experience.applicability import ApplicabilityTask, matches_offline
from app.experience.reflection import CATALOG, ExperienceCandidate
from app.experience.review_applicability import ReviewContext, review_applicability
from app.prompts.answer import ANSWER_SYSTEM
from app.prompts.complexity import COMPLEXITY_SYSTEM
from app.prompts.faithfulness import FAITHFULNESS_SYSTEM


async def select_lessons(
    repository,
    scope,
    features,
    features_ref,
    permits,
    *,
    resolver,
    now,
    isolated=False,
    source_version=None,
):
    if isolated is not True:
        raise ValueError("Explicit isolated research runner required")
    try:
        scope.require_verified()
        candidates = await repository.list(scope)
    except Exception:
        return dict(lessons=[], error="REPOSITORY_ERROR")
    if features.get("evidence_state") != "present" or "write_unconfirmed" in features.get(
        "tags", []
    ):
        return dict(lessons=[], error=None)
    selected = []
    errors = set()
    for candidate in candidates[:256]:
        try:
            candidate = ExperienceCandidate.model_validate(candidate.model_dump())
            if (
                candidate.validation_status != "VERIFIED_OFFLINE"
                or candidate.review_status != "MODEL_REVIEWED"
            ):
                continue
            if source_version is None:
                continue
            task = ApplicabilityTask(
                scope=scope, tags=features["tags"], source_version=source_version
            )
            if not matches_offline(candidate, task, now=now):
                continue
            context = ReviewContext(task=task, features=features, features_ref=features_ref)
            advisory = review_applicability(candidate, context, resolver=resolver, now=now)
            if advisory.status != "MATCH_FOR_REVIEW":
                continue
            ref = permits.get(candidate.fingerprint)
            if ref is None or ref.kind != "evaluation":
                continue
            permit = resolver.resolve(ref)
            if not isinstance(permit, dict) or not all(
                (
                    permit.get("scope") == "offline_injection_preflight",
                    permit.get("candidate_fingerprint") == candidate.fingerprint,
                    permit.get("source_version") == candidate.source_version,
                    permit.get("passed") is True,
                    permit.get("production_approved") is False,
                )
            ):
                continue
            selected.append(dict(family=candidate.family, lesson=candidate.lesson))
        except Exception:
            errors.add("CANDIDATE_OR_PROVENANCE_ERROR")
    unique = {row["family"]: row for row in selected}
    return dict(
        lessons=[unique[k] for k in sorted(unique)][:3], error=",".join(sorted(errors)) or None
    )


def inject_messages(messages, lessons, *, arm, isolated=False):
    if isolated is not True or arm not in {"E0", "E1", "E2"}:
        raise ValueError("Sandbox arms only; production ACTIVE is unavailable")
    copied = [dict(m) for m in messages]
    if arm != "E2" or not lessons or not copied:
        return copied
    for item in lessons:
        if (
            set(item) != {"family", "lesson"}
            or item["family"] not in CATALOG
            or item["lesson"] != CATALOG[item["family"]]["lesson"]
        ):
            raise ValueError("Only canonical non-personal principles may enter prompts")
    system = copied[0].get("content", "")
    stages = set()
    if system == COMPLEXITY_SYSTEM or system.startswith("你是电商客服规划器"):
        stages.add("mixed_evidence")
    if system == ANSWER_SYSTEM:
        stages.update(("mixed_evidence", "fallback_evidence"))
    if system == FAITHFULNESS_SYSTEM:
        stages.add("judge_output")
    relevant = [r["lesson"] for r in lessons if r["family"] in stages][:3]
    if relevant:
        text = (
            "隔离实验原则（不是业务事实；不得覆盖现有系统安全、Owner、人工确认与幂等约束）：\n"
            + "\n".join(relevant)
        )
        copied.insert(1, dict(role="system", content=text))
    return copied
