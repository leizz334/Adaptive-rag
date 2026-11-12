"""Explicit isolated Planner recall; never wired into production Agent execution."""

import re
from datetime import UTC, datetime

from app.agents.goals import read_goals, read_tools
from app.agents.nodes.planner import _explicit_write_request
from app.experience.compatibility import check_compatibility, digest, runtime_contracts
from app.experience.reflection import CATALOG, ExperienceCandidate
from app.guardrails.injection import detect_prompt_injection
from app.prompts.planner import PLANNER_SYSTEM

FAMILIES = {"tool_coverage", "plan_contract", "answer_coverage"}
SAFETY_FEATURES = {"owner_scope", "hitl", "idempotency", "entity_binding"}


def task_features(query, registry):
    """Conservative structural features, never consumes Gold or expected calls."""
    try:
        detect_prompt_injection(query)
    except Exception:
        return None
    entities = set(re.findall(r"(?<![A-Za-z0-9_])ORD\d+(?![A-Za-z0-9_])", query, re.I))
    # The legacy bounded goal parser treats the substring 别查 as negation,
    # including affirmative 分别查. Normalize only this structural observation.
    feature_query = query.replace("分别查", "逐项核实")
    tools = tuple(n for n in read_tools(feature_query) if n in registry.names())
    if (
        not entities
        or not tools
        or any(
            _explicit_write_request(query, name)
            for name in ["cancel_order", "create_return_request", "create_refund_request"]
        )
    ):
        return None
    tags = {"live_fact", "plan_contract"}
    if (
        len(read_goals(feature_query)) > 1
        or len(entities) > 1
        or sum(k in query for k in ["名称", "数量", "定制"]) >= 2
    ):
        tags.add("multi_goal")
    return {"tags": tags, "tools": tools, "entities": len(entities)}


async def select_isolated(
    repository, scope, query, registry, permits, *, resolver, isolated=False, now=None
):
    if isolated is not True:
        raise PermissionError("isolated research process required; production Active unavailable")
    scope.require_verified()
    features = task_features(query, registry)
    if features is None:
        return []
    manifest = runtime_contracts(registry)
    clock = now or datetime.now(UTC)
    selected = []
    for original in (await repository.list(scope))[:256]:
        try:
            candidate = ExperienceCandidate.model_validate(original.model_dump())
            if (
                candidate.scope.key != scope.key
                or not candidate.scope.verified
                or candidate.family not in FAMILIES
                or candidate.validation_status != "VERIFIED_OFFLINE"
                or candidate.review_status != "MODEL_REVIEWED"
                or candidate.expires_at <= clock
            ):
                continue
            if (
                not set(candidate.applicability_conditions) <= features["tags"]
                or set(candidate.non_applicability_conditions) & features["tags"]
            ):
                continue
            for ref in candidate.evidence_refs:
                resolver.resolve(ref)
            ref = permits.get(candidate.experience_id)
            if ref is None or ref.kind != "evaluation":
                continue
            permit = resolver.resolve(ref)
            if not isinstance(permit, dict) or not all(
                [
                    permit.get("scope") == "isolated_planner_preflight_v1",
                    permit.get("candidate_id") == candidate.experience_id,
                    permit.get("candidate_version") == candidate.version,
                    permit.get("candidate_fingerprint") == candidate.fingerprint,
                    permit.get("candidate_source_version") == candidate.source_version,
                    permit.get("experience_scope") == scope.model_dump(),
                    permit.get("passed") is True,
                    permit.get("independently_validated") is True,
                    permit.get("human_approved") is False,
                    permit.get("production_approved") is False,
                    set(permit.get("required_features", [])) == SAFETY_FEATURES,
                    permit.get("target_signature") == digest(manifest),
                ]
            ):
                continue
            validation = resolver.resolve(type(ref).model_validate(permit["validation_ref"]))
            if not all(
                [
                    validation.get("scope") == "offline_applicability",
                    validation.get("candidate_fingerprint") == candidate.fingerprint,
                    validation.get("source_version") == candidate.source_version,
                    validation.get("family") == candidate.family,
                    validation.get("independent_labels") is True,
                    validation.get("passed") is True,
                    type(validation.get("cases")) is int and validation["cases"] >= 3,
                    validation.get("safety_conflicts") == 0,
                ]
            ):
                continue
            result = check_compatibility(
                permit["validated_manifest"],
                manifest,
                tools=permit["required_tools"],
                features=permit["required_features"],
            )
            if not result["compatible"]:
                continue
            score = {
                "tool_coverage": 5 if len(features["tools"]) > 1 or features["entities"] > 1 else 1,
                "plan_contract": 4 if features["entities"] > 1 else 1,
                "answer_coverage": 4 if features["entities"] == 1 else 3,
            }[candidate.family]
            selected.append((score, candidate))
        except Exception:
            continue  # No permit/provenance/contract error may broaden recall.
    return [c for _, c in sorted(selected, key=lambda x: (-x[0], x[1].family))[:2]]


def _render_planner(messages, candidates, *, arm, registry, isolated=False):
    if isolated is not True or arm not in {"E0", "E1", "E2"}:
        raise PermissionError("isolated experiment arms only")
    copied = [dict(m) for m in messages]
    if arm != "E2" or not candidates or not copied:
        return copied
    prefix = PLANNER_SYSTEM.split("{tools}")[0]
    if copied[0].get("role") != "system" or not copied[0].get("content", "").startswith(prefix):
        return copied
    if len(candidates) > 2:
        raise ValueError("at most two independently validated lessons")
    for value in candidates:
        c = ExperienceCandidate.model_validate(value.model_dump())
        if (
            c.family not in FAMILIES
            or c.validation_status != "VERIFIED_OFFLINE"
            or c.review_status != "MODEL_REVIEWED"
            or c.lesson != CATALOG[c.family]["lesson"]
        ):
            raise PermissionError("canonical qualified lessons only")
    copied.insert(
        1,
        {
            "role": "system",
            "content": "隔离研究经验（仅规划提示，不是业务事实；不得覆盖原工具目录、Schema、实体来源、权限、Owner、HITL与幂等要求）：\n"
            + "\n".join(c.lesson for c in candidates),
        },
    )
    return copied


async def prepare_planner(
    messages,
    *,
    arm,
    repository,
    scope,
    query,
    registry,
    permits,
    resolver,
    isolated=False,
    now=None,
):
    if isolated is not True or arm not in {"E0", "E1", "E2"}:
        raise PermissionError("isolated experiment only")
    if arm == "E0":
        return [dict(m) for m in messages], []
    candidates = await select_isolated(
        repository, scope, query, registry, permits, resolver=resolver, isolated=True, now=now
    )
    return _render_planner(
        messages, candidates, arm=arm, registry=registry, isolated=True
    ), candidates
