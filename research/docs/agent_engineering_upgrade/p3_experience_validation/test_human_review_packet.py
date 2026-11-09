"""Offline provenance and human-gate contract for the seven-answer review delivery."""

import csv
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "prepare_human_review", HERE / "prepare_human_review.py"
)
packet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packet)


class HumanReviewPacketTests(unittest.TestCase):
    def test_seven_exact_public_answers_and_queries_not_drafts(self):
        cases, _, _ = packet.load_verified_cases()
        self.assertEqual(tuple(case["case_id"] for case in cases), packet.CASES)
        rendered = packet.build_outputs()["P3-B1_HUMAN_REVIEW_PACKET.md"].decode("utf-8")
        for case in cases:
            for field, ref in (
                ("query", "query_ref"),
                ("public_final_answer", "public_answer_ref"),
            ):
                self.assertEqual(case[field], packet.resolve_ref(case[ref]))
                self.assertIn(packet.fenced(case[field]), rendered)
            self.assertEqual(
                case["public_answer_ref"]["json_pointer"], "/traces/0/turns/0/response/answer"
            )
        self.assertNotIn("answer_versions", rendered)
        self.assertNotIn("synthetic_final_database", rendered)

    def test_csv_bom_rows_blank_human_fields_and_hashes(self):
        outputs = packet.build_outputs()
        data = outputs["human_review_template.csv"]
        self.assertTrue(data.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))
        self.assertEqual(len(rows), 7)
        cases, _, _ = packet.load_verified_cases()
        for row, case in zip(rows, cases, strict=True):
            self.assertEqual(tuple(row), packet.COLUMNS)
            self.assertEqual(row["case_id"], case["case_id"])
            self.assertEqual(row["answer_sha256"], packet.sha_text(case["public_final_answer"]))
            self.assertEqual(row["query_sha256"], packet.sha_text(case["query"]))
            self.assertTrue(all(row[key] == "" for key in packet.HUMAN_COLUMNS))
            self.assertFalse(
                any(value.lstrip().startswith(("=", "+", "-", "@")) for value in row.values())
            )

    def test_chinese_quoted_multiline_csv_round_trip(self):
        sample = {key: "" for key in packet.COLUMNS}
        sample["case_id"] = "PSV04"
        sample["notes"] = '中文，含逗號, "引號"\n第二行'
        encoded = packet.csv_bytes([sample])
        decoded = next(csv.DictReader(io.StringIO(encoded.decode("utf-8-sig"), newline="")))
        self.assertEqual(decoded, sample)

    def test_manifest_provenance_hashes_csv_cells_and_human_gate(self):
        outputs = packet.build_outputs()
        manifest = json.loads(outputs["evidence/b1_packet_validation.json"])
        self.assertEqual(manifest["human_review_status"], "PENDING_HUMAN_REVIEW")
        self.assertEqual(manifest["human_verdicts_populated"], 0)
        self.assertEqual(manifest["public_answer_count"], 7)
        self.assertGreater(manifest["verified_json_references"], 100)
        for item in manifest["inputs"]:
            self.assertEqual(packet.sha_file(packet.ROOT / item["file"]), item["sha256"])
        for name, digest in manifest["output_sha256"].items():
            self.assertEqual(hashlib.sha256(outputs[name]).hexdigest(), digest)
        self.assertEqual(manifest["csv_cell_count"], 7 * len(packet.COLUMNS))
        self.assertEqual(len(manifest["csv_cell_sha256"]), 7)
        index = outputs["P3-B1_HUMAN_REVIEW_INDEX.md"].decode("utf-8")
        for case in packet.CASES:
            self.assertIn(f"#{case.lower()}", index)
        for name in packet.USER_DELIVERABLES:
            self.assertIn(f"{packet.PHASE_REL}/{name}", index)
            self.assertIn(f"{packet.DELIVERY_ABSOLUTE}/{name}", index)

    def test_ai_disagreement_is_folded_after_blind_evidence(self):
        text = packet.build_outputs()["P3-B1_HUMAN_REVIEW_PACKET.md"].decode("utf-8")
        for case in packet.CASES:
            section = text.split(f'<a id="{case.lower()}"></a>', 1)[1].split('<a id="', 1)[0]
            self.assertLess(section.index("實際工具與 RAG 證據"), section.index("<details>"))
            self.assertIn("非人工判定", section)
        self.assertIn("MODEL_ASSISTED_REVIEW_DISAGREEMENT", text)
        self.assertIn("UNCERTAIN", text)

    def test_frozen_write_refuses_overwrite_of_human_review(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            packet.write_frozen_outputs(directory)
            packet.check_frozen_outputs(directory)
            target = directory / "human_review_template.csv"
            target.write_text("human supplied edits", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                packet.write_frozen_outputs(directory)
            self.assertEqual(target.read_text(encoding="utf-8"), "human supplied edits")


if __name__ == "__main__":
    unittest.main()
