"""Normalize independently reviewed saved evidence; never consumes live requests."""

import json

from app.experience.contracts import EvidenceRef
from app.experience.taxonomy import classify_failure
from research.docs.agent_engineering_upgrade.p3_experience_shadow.manage import (
    BASE,
    HERE,
    ROOT,
    save,
    sha,
)


def resolve(value, pointer):
    for part in pointer.split("/")[1:] if pointer else []:
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def main(output=None):
    diagnoses = json.loads((HERE / "evidence/a2_trace_diagnoses.json").read_bytes())
    sources = diagnoses["source_registry"]
    for source in sources.values():
        assert sha(ROOT / source["path"]) == source["sha256"]
    assessments = []
    pointers = 0
    for cohort in ("p2s_real14", "p2r_supplementary", "evaluation_artifacts"):
        for row in diagnoses[cohort]:
            refs = []
            for ref in row["evidence_refs"]:
                source = sources[ref["source_id"]]
                path = ROOT / source["path"]
                if source["format"] == "json":
                    resolve(json.loads(path.read_bytes()), ref["json_pointer"])
                    pointers += 1
                refs.append(
                    EvidenceRef(
                        artifact=source["path"],
                        sha256=source["sha256"],
                        pointer=ref["json_pointer"],
                        kind="evaluation" if "contract" in ref.get("role", "") else "trace",
                    )
                )
            state = row["record_status"]
            proof = (
                "SCORER_ARTIFACT"
                if state == "EVALUATION_ARTIFACT"
                else "TRACE_CONTRACT"
                if state == "VERIFIED_FAILURE"
                else "SUCCESS_CONTROL"
                if row.get("negative_control")
                else "MODEL_REVIEW"
                if state == "LIKELY_FAILURE"
                else "SCORE_ONLY"
            )
            category = row.get("primary_category") or "UNKNOWN"
            node = row.get("first_error_node") or "unlocalized"
            if isinstance(node, dict):
                node = node["node"]
            if state == "EVALUATION_ARTIFACT":
                node = "answer_evaluator"
            chain = row.get("actual_node_chain") or row.get("causal_chain") or []
            signals = [
                dict(
                    category=category,
                    proof=proof,
                    node=node,
                    position=chain.index(node) if node in chain else 0,
                    evidence_refs=refs[:16],
                    summary="Observed frozen contract divergence"
                    if state == "VERIFIED_FAILURE"
                    else "Scoped control or evaluator observation",
                    root_cause_hypothesis="Mechanism remains a hypothesis; inspect the independently reviewed evidence and alternatives",
                    context_tags=["live_fact", "static_policy"]
                    if category == "ROUTING_ERROR"
                    and {"get_product_detail", "get_price"}
                    <= {t["name"] for t in row.get("required_tools", [])}
                    else [],
                )
            ]
            value = classify_failure(
                source_trace_id=row["diagnosis_id"],
                source_case_id=row["case_id"],
                source_version=BASE,
                signals=signals,
            )
            assessments.append(
                dict(
                    cohort=cohort,
                    diagnosis_id=row["diagnosis_id"],
                    assessment=value.model_dump(mode="json"),
                    reviewed_level=state,
                    reviewed_primary=category,
                )
            )
    matched = sum(
        r["assessment"]["evidence_level"] == r["reviewed_level"]
        and r["assessment"]["failure_type"] == r["reviewed_primary"]
        for r in assessments
    )
    save(
        output or HERE / "evidence/a2_normalized_assessments.json",
        dict(
            schema="p3a-trusted-signal-normalization-v1",
            source_version_semantics="Immutable evidence package version; original runtime hashes remain in referenced run configs",
            rows=assessments,
            validation=dict(
                sources=len(sources),
                pointers=pointers,
                reviewed_label_reproduction=f"{matched}/{len(assessments)}",
                independence="Not a blind root-cause accuracy estimate: classifier consumes reviewed structural signals",
                new_api_calls=0,
            ),
        ),
    )
    print(
        json.dumps(
            dict(
                sources=len(sources),
                pointers=pointers,
                assessment_count=len(assessments),
                reviewed_label_reproduction=f"{matched}/{len(assessments)}",
            )
        )
    )


if __name__ == "__main__":
    main()
