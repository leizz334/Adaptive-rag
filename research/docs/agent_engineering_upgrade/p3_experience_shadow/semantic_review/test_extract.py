"""Local saved-fixture checks of the semantic review's provenance contract."""

import hashlib
import importlib.util
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("semantic_extract", HERE / "extract.py")
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)


class ReviewEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = extract.read(HERE / "evidence_packet.json")
        cls.report = extract.read(HERE / "semantic_review.json")

    def test_exact_denominator_and_no_supplementary_leak(self):
        expected = {f"{case}:{arm}:0" for case in extract.CASES for arm in ("R0", "R1")}
        self.assertEqual(len(expected), 14)
        self.assertEqual({e["id"] for e in self.packet["answers"]}, expected)
        self.assertEqual({e["id"] for e in self.report["answers"]}, expected)
        appendix = self.report["supplementary"]
        self.assertFalse(appendix["included_in_main_denominator"])
        self.assertEqual(len(appendix["records"]), 4)
        self.assertTrue(all(e["semantic_status"] == "NOT_ASSESSED" for e in appendix["records"]))

    def test_all_json_references_and_sha256_resolve(self):
        # Includes every atomic claim and the separate immutable historical score refs.
        seen = 0

        def visit(value):
            nonlocal seen
            if isinstance(value, dict):
                if {"file", "sha256", "json_pointer"} <= set(value):
                    source = extract.ROOT / value["file"]
                    self.assertEqual(
                        hashlib.sha256(source.read_bytes()).hexdigest(), value["sha256"]
                    )
                    extract.pointer(extract.read(source), value["json_pointer"])
                    seen += 1
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(self.packet)
        visit(self.report)
        self.assertGreater(seen, 250)

    def test_public_final_answer_not_generated_draft(self):
        for ev in self.packet["answers"]:
            source = extract.read(extract.ROOT / ev["public_answer_ref"]["file"])
            self.assertEqual(
                ev["public_final_answer"],
                extract.pointer(source, ev["public_answer_ref"]["json_pointer"]),
            )
        ev = next(e for e in self.packet["answers"] if e["id"] == "PSV22:R0:0")
        self.assertEqual(ev["public_final_answer"], "订单 ORD10002 当前状态：已签收。")
        self.assertTrue(any("退款单" in a["text"] for a in ev["answer_versions"]))
        r = next(e for e in self.report["answers"] if e["id"] == "PSV22:R0:0")
        self.assertEqual(r["dimensions"]["completeness"], "FAIL")

    def test_packet_excludes_hidden_reasoning_and_session_storage(self):
        forbidden = {
            "reasoning_content",
            "reasoning",
            "analysis",
            "messages",
            "selected_context",
            "plan",
            "history",
            "tables",
            "input",
            "prompt",
            "response",
        }

        def visit(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden & set(value))
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(self.packet)
        self.assertFalse(self.packet["contains_hidden_reasoning"])
        for ev in self.packet["answers"]:
            self.assertEqual(
                set(ev["synthetic_final_database"]["orders"]), {"ORD10001", "ORD10002", "ORD10003"}
            )
            self.assertTrue(
                all(
                    o["user_id"] == "u_demo"
                    for o in ev["synthetic_final_database"]["orders"].values()
                )
            )

    def test_deterministic_value_checks_do_not_claim_semantic_review(self):
        observed = 0
        missing = 0
        for ev in self.packet["answers"]:
            for check in ev["deterministic_tool_value_checks"]:
                self.assertEqual(check["method"], "DETERMINISTIC_TOOL_VALUE_COMPARISON")
                self.assertTrue(check["does_not_judge_final_answer_text"])
                if check["status"] == "NOT_OBSERVED":
                    missing += 1
                else:
                    observed += 1
                    actual = check["actual"]
                    expected = check["expected"]
                    passed = (
                        actual == expected if check["comparison"] == "eq" else expected in actual
                    )
                    self.assertEqual(check["status"], "PASS" if passed else "FAIL")
                    if passed:
                        self.assertEqual(check["assurance"], "DETERMINISTIC_VERIFIED")
        self.assertGreater(observed, 15)
        self.assertGreater(missing, 5)

    def test_manual_verdicts_unknowns_and_human_not_run(self):
        self.assertEqual(self.report["review_method"], "MODEL_ASSISTED_REVIEW")
        self.assertEqual(self.report["HUMAN_CALIBRATION"], "NOT_RUN")
        for row in self.report["answers"]:
            self.assertEqual(row["review_method"], "MODEL_ASSISTED_REVIEW")
            self.assertEqual(
                set(row["dimensions"]),
                {"factual_correctness", "completeness", "faithfulness", "safety"},
            )
            self.assertEqual(row["HUMAN_CALIBRATION"], "NOT_RUN")
            self.assertTrue(row["claims"])
            for claim in row["claims"]:
                self.assertIn(claim["status"], {"PASS", "FAIL", "NOT_ASSESSED"})
                self.assertTrue(claim["evidence_refs"])
        warranty = next(e for e in self.report["answers"] if e["id"] == "PSV16:R1:0")
        self.assertEqual(warranty["overall"], "NOT_ASSESSED")
        self.assertIn("UNSUPPORTED_ADDITIONAL_CLAIM", warranty["errors"])
        residual = next(e for e in self.report["answers"] if e["id"] == "PSV04:R1:0")
        self.assertEqual(residual["initial_independent_model_overall"], "PASS")
        self.assertEqual(residual["overall"], "NOT_ASSESSED")
        self.assertEqual(len(residual["review_disagreements"]), 1)
        self.assertEqual(residual["dimensions"]["completeness"], "PASS")

    def test_frozen_clock_dates_and_historical_v20_preserved(self):
        for arm in ("R0", "R1"):
            ev = next(e for e in self.packet["answers"] if e["id"] == f"PSD03:{arm}:0")
            self.assertIn("2026-10-24", ev["public_final_answer"])
            self.assertTrue(ev["tool_calls"][0]["output"]["delivered_at"].startswith("2026-10-24"))
            self.assertEqual(ev["original_saved_score"]["schema_version"], "answer-eval-v2.0")
            self.assertEqual(ev["original_saved_score"]["OVERALL_TASK_SUCCESS"], "FAIL")
            self.assertEqual(ev["v21_saved_score"]["schema_version"], "answer-eval-v2.1")


if __name__ == "__main__":
    unittest.main()
