"""Explicit user-attested answer review import; never experience approval."""

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

from research.docs.agent_engineering_upgrade.p3_experience_validation import (
    prepare_human_review as p,
)

DIMENSIONS = ("factual_correctness", "completeness", "faithfulness", "safety")
VERDICTS = ("PASS", "FAIL", "UNCERTAIN")


def validate_rows(rows, *, attested_by_user=False):
    if attested_by_user is not True:
        raise ValueError("Explicit user submission attestation required")
    cases, _, _ = p.load_verified_cases()
    expected = {c["case_id"]: c for c in cases}
    if len(rows) != len(expected) or {r.get("case_id") for r in rows} != set(expected):
        raise ValueError("Exactly seven unique original cases required")
    for row in rows:
        if set(row) != set(p.COLUMNS) or any(not isinstance(v, str) for v in row.values()):
            raise ValueError("Unexpected or missing CSV fields")
        case = expected[row["case_id"]]
        if row["answer_sha256"] != p.sha_text(case["public_final_answer"]) or row[
            "query_sha256"
        ] != p.sha_text(case["query"]):
            raise ValueError("Frozen query/answer identity mismatch")
        if any(row[k] not in VERDICTS for k in (*DIMENSIONS, "overall_verdict")):
            raise ValueError("Human verdict must be PASS/FAIL/UNCERTAIN")
        dimensions = [row[k] for k in DIMENSIONS]
        overall = (
            "FAIL" if "FAIL" in dimensions else "UNCERTAIN" if "UNCERTAIN" in dimensions else "PASS"
        )
        if row["overall_verdict"] != overall:
            raise ValueError("Overall disagrees with dimension contract")
        for name in ("reviewer_name", "reviewed_at", "notes"):
            value = row[name]
            if len(value) > 4000 or value.lstrip().startswith(("=", "+", "-", "@")):
                raise ValueError("Unsafe or oversized review metadata")
        if row["reviewed_at"]:
            try:
                value = datetime.fromisoformat(row["reviewed_at"])
                if value.tzinfo is None:
                    raise ValueError("Review time requires timezone")
            except ValueError as exc:
                raise ValueError("Invalid supplied review timestamp") from exc
    return dict(
        schema="user-answer-review-v1",
        method="USER_SUBMITTED_REVIEW",
        calibration_status="PARTIAL",
        multi_rater_agreement="NOT_ASSESSED",
        experience_approval=False,
        rows=rows,
        overall_counts={v: sum(r["overall_verdict"] == v for r in rows) for v in VERDICTS},
        dimension_counts={
            k: {v: sum(r[k] == v for r in rows) for v in VERDICTS} for k in DIMENSIONS
        },
        missing_reviewer_rows=sum(not r["reviewer_name"] for r in rows),
        missing_review_time_rows=sum(not r["reviewed_at"] for r in rows),
        missing_notes_rows=sum(not r["notes"] for r in rows),
        metadata_policy="Unknown fields stay blank; import time is not review time; no human experience approval inferred",
    )


def import_review(source: Path, output: Path, *, attested_by_user=False):
    raw = source.read_bytes()
    text = raw.decode("utf-8-sig", errors="strict")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != list(p.COLUMNS):
        raise ValueError("Exact unique original CSV headers required")
    report = validate_rows(list(reader), attested_by_user=attested_by_user)
    output.mkdir(parents=True, exist_ok=False)
    (output / "submitted_review.csv").write_bytes(raw)
    report.update(
        input_sha256=hashlib.sha256(raw).hexdigest(),
        imported_at=datetime.now(UTC).isoformat(),
        attestation="User stated on 2026-11-10 that the CSV contains their reviewed results and explicitly continued B2",
    )
    (output / "import_report.json").write_bytes(
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
    )
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--user-attested", action="store_true")
    args = parser.parse_args()
    value = import_review(args.source, args.output, attested_by_user=args.user_attested)
    print(
        json.dumps(
            {
                k: value[k]
                for k in (
                    "overall_counts",
                    "calibration_status",
                    "experience_approval",
                    "input_sha256",
                )
            }
        )
    )
