"""Classify trusted offline structural signals, never infer a cause from score."""

from app.experience.contracts import FailureAssessment, FailureSignal, FailureType, Proof


def classify_failure(*, source_trace_id, source_case_id, source_version, signals):
    if len(signals) > 64:
        raise ValueError("Bounded trace signals required")
    ordered = sorted(
        [s if isinstance(s, FailureSignal) else FailureSignal.model_validate(s) for s in signals],
        key=lambda s: s.position,
    )
    observed = [
        s
        for s in ordered
        if s.proof in {Proof.TRACE_CONTRACT, Proof.RUNTIME_ERROR}
        and s.category not in {FailureType.UNKNOWN, FailureType.EVALUATION_CONTRACT_ISSUE}
    ]
    likely = [s for s in ordered if s.proof == Proof.MODEL_REVIEW]
    artifacts = [s for s in ordered if s.proof == Proof.SCORER_ARTIFACT]
    selected = (observed or likely or artifacts or [None])[0]
    level = (
        "VERIFIED_FAILURE"
        if observed
        else "LIKELY_FAILURE"
        if likely
        else "EVALUATION_ARTIFACT"
        if artifacts
        else "UNDETERMINED"
    )
    refs = list(
        {
            (r.artifact, r.sha256, r.pointer, r.kind): r for s in ordered for r in s.evidence_refs
        }.values()
    )[:64]
    return FailureAssessment(
        source_trace_id=source_trace_id,
        source_case_id=source_case_id,
        source_version=source_version,
        failure_type=selected.category if selected else FailureType.UNKNOWN,
        evidence_level=level,
        first_error_node=selected.node if selected else None,
        direct_failure=selected.summary if selected else "No independently localized failure",
        root_cause_hypothesis=selected.root_cause_hypothesis
        if selected
        else "Unknown; score alone does not identify a root cause",
        confidence="HIGH" if observed or artifacts else "MEDIUM" if likely else "LOW",
        confidence_source=selected.proof.value if selected else "INSUFFICIENT_EVIDENCE",
        evidence_refs=refs,
        propagation=[s.category.value for s in ordered if s in observed],
        alternative_explanations=list(dict.fromkeys(s.category.value for s in likely)),
    )
