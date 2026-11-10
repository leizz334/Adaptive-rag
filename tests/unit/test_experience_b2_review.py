"""Independent, implementation-aware counterexamples; no Agent/model execution."""

import csv
import hashlib
import io
import json
from datetime import UTC, datetime, timedelta

import pytest

from app.experience.contracts import EvidenceRef, ExperienceScope
from app.experience.reflection import CATALOG, ExperienceCandidate
from app.experience.shadow import EvidenceResolver
from research.docs.agent_engineering_upgrade.p3_experience_validation import (
    human_import,
    sandbox,
)


def write_ref(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return EvidenceRef(
        artifact=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), kind="evaluation"
    )


@pytest.mark.parametrize("unsafe", ["unknown_evidence", "empty_evidence", "pending_write"])
async def test_independent_unknown_or_pending_context_never_injects(unsafe, tmp_path):
    now = datetime(2026, 11, 10, tzinfo=UTC)
    source = "a" * 40
    template = CATALOG["mixed_evidence"]
    scope = ExperienceScope(
        tenant_ref="1" * 64, user_ref="2" * 64, session_ref="3" * 64, verified=True
    )
    provenance = write_ref(tmp_path, "source.json", {"synthetic": True})
    item = ExperienceCandidate(
        scope=scope,
        source_trace_id="independent.synthetic",
        source_case_id="independent.synthetic",
        failure_type="ROUTING_ERROR",
        evidence_refs=[provenance],
        family="mixed_evidence",
        lesson=template["lesson"],
        applicability_conditions=template["required"],
        non_applicability_conditions=template["excluded"],
        validation_status="VERIFIED_OFFLINE",
        review_status="MODEL_REVIEWED",
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(days=1),
        source_version=source,
    )
    features = dict(
        tags=["live_fact", "static_policy"],
        evidence_state={"unknown_evidence": "unknown", "empty_evidence": "empty"}.get(
            unsafe, "present"
        ),
        annotation_verified=True,
    )
    if unsafe == "pending_write":
        features["tags"].append("write_unconfirmed")
    features_ref = write_ref(tmp_path, "features.json", features)
    permit = write_ref(
        tmp_path,
        "permit.json",
        dict(
            scope="offline_injection_preflight",
            candidate_fingerprint=item.fingerprint,
            source_version=source,
            passed=True,
            production_approved=False,
        ),
    )

    class Repository:
        async def list(self, identity):
            assert identity == scope
            return [item]

    result = await sandbox.select_lessons(
        Repository(),
        scope,
        features,
        features_ref,
        {item.fingerprint: permit},
        resolver=EvidenceResolver(tmp_path),
        now=now,
        isolated=True,
        source_version=source,
    )
    assert result["lessons"] == []


def test_independent_duplicate_csv_header_is_rejected(tmp_path, monkeypatch):
    cases = [
        dict(case_id=f"CASE{i}", query=f"query{i}", public_final_answer=f"answer{i}")
        for i in range(7)
    ]
    monkeypatch.setattr(human_import.p, "load_verified_cases", lambda: (cases, {}, []))
    columns = list(human_import.p.COLUMNS) + ["safety"]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(columns)
    for case in cases:
        row = dict(
            case_id=case["case_id"],
            answer_sha256=human_import.p.sha_text(case["public_final_answer"]),
            query_sha256=human_import.p.sha_text(case["query"]),
            factual_correctness="PASS",
            completeness="PASS",
            faithfulness="PASS",
            safety="FAIL",
            overall_verdict="PASS",
            reviewer_name="",
            reviewed_at="",
            notes="",
        )
        # DictReader silently discards the first safety=FAIL under duplicate headers.
        writer.writerow([row[key] for key in human_import.p.COLUMNS] + ["PASS"])
    source = tmp_path / "review.csv"
    source.write_text(stream.getvalue(), encoding="utf-8")
    output = tmp_path / "import"
    with pytest.raises(ValueError):
        human_import.import_review(source, output, attested_by_user=True)
    assert not output.exists()
