"""Tool/feature compatibility is advisory and never grants experience approval."""

import hashlib
import inspect
import json


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def runtime_contracts(registry):
    from app.agents.nodes.planner import _sanitize_plan
    from app.repositories.idempotency import IdempotencyRepository
    from app.repositories.session_repository import SessionRepository
    from app.services.chat_service import ChatService

    functions = {
        "owner_scope": SessionRepository.get_or_create,
        "hitl": ChatService._load_confirmation,
        "idempotency": IdempotencyRepository.put,
        "entity_binding": _sanitize_plan,
    }
    return {
        "tools": {
            t.name: digest(
                {
                    "schema": t.input_model.model_json_schema(),
                    "risk": t.risk.value,
                    "description": t.description,
                }
            )
            for t in registry.all()
        },
        "features": {
            name: hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()
            for name, fn in functions.items()
        },
    }


def check_compatibility(validated_manifest, current_manifest, *, tools, features):
    """A matching Git hash is neither necessary nor sufficient. No status changes."""
    if not tools or not features:
        return {"compatible": False, "reason": "UNSPECIFIED_CONTRACT", "approval_granted": False}
    for group, names in [("tools", tools), ("features", features)]:
        for name in names:
            value = validated_manifest.get(group, {}).get(name)
            if not value or current_manifest.get(group, {}).get(name) != value:
                return {
                    "compatible": False,
                    "reason": "CONTRACT_CHANGED",
                    "approval_granted": False,
                }
    return {"compatible": True, "reason": "REQUIRED_CONTRACTS_EQUAL", "approval_granted": False}
