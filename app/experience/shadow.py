"""Completed-trace observation only. No imports or hooks into Agent execution."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.experience.contracts import EvidenceRef, ExperienceScope, FailureAssessment
from app.experience.reflection import reflect


class EvidenceResolver:
    def __init__(self, root: Path, *, max_bytes=5_000_000):
        self.root = Path(root).resolve()
        self.max_bytes = max_bytes

    def resolve(self, reference: EvidenceRef):
        ref = EvidenceRef.model_validate(reference.model_dump())
        path = (self.root / ref.artifact).resolve()
        if (
            not path.is_relative_to(self.root)
            or path.suffix != ".json"
            or path.stat().st_size > self.max_bytes
        ):
            raise ValueError("Bounded local JSON evidence required")
        raw = path.read_bytes()
        if len(raw) > self.max_bytes or hashlib.sha256(raw).hexdigest() != ref.sha256:
            raise ValueError("Evidence hash conflict")
        value = json.loads(raw)
        for part in ref.pointer.split("/")[1:] if ref.pointer else []:
            key = part.replace("~1", "/").replace("~0", "~")
            if isinstance(value, list):
                if not re.fullmatch(r"0|[1-9][0-9]*", key):
                    raise ValueError("Canonical non-negative array index required")
                value = value[int(key)]
            else:
                value = value[key]
        return value


@dataclass(frozen=True)
class ObservationOutcome:
    status: str
    experience_id: str | None = None


class ShadowObserver:
    def __init__(self, *, mode="off", resolver=None, sink=None, max_observations=64, clock=None):
        if mode not in {"off", "shadow"} or not 1 <= max_observations <= 256:
            raise ValueError("Off/shadow mode and bounded observation limit required")
        self.mode, self.resolver, self.sink = mode, resolver, sink
        self.limit = max_observations
        self.clock = clock or (lambda: datetime.now(UTC))
        self.seen: set[tuple] = set()

    async def observe(
        self,
        completed_result,
        assessment: FailureAssessment,
        scope: ExperienceScope,
        *,
        completed: bool,
    ):
        # completed_result is deliberately never passed to reflection/sink or
        # mutated. Its shape/content is irrelevant to offline experience analysis.
        if self.mode == "off":
            return ObservationOutcome("OFF")
        if completed is not True:
            return ObservationOutcome("INCOMPLETE")
        try:
            scope.require_verified()
            key = (*scope.key, assessment.source_trace_id, assessment.source_version)
            if key in self.seen:
                return ObservationOutcome("SKIPPED_DUPLICATE")
            if len(self.seen) >= self.limit:
                return ObservationOutcome("SKIPPED_LIMIT")
            self.seen.add(key)
            candidate = reflect(assessment, scope, now=self.clock())
            if candidate is None:
                return ObservationOutcome("NO_SAFE_LESSON")
            if self.resolver is None:
                raise ValueError("Explicit offline evidence resolver required")
            for ref in candidate.evidence_refs:
                self.resolver.resolve(ref)
            if self.sink:
                await self.sink(candidate)
            return ObservationOutcome("PROPOSED", candidate.experience_id)
        except Exception:
            # Error category only: no raw exception, user data or credential log.
            return ObservationOutcome("ERROR")
