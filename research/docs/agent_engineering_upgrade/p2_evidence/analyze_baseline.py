"""Read immutable real-run evidence offline; no provider/client sends requests."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def main():
    run = ROOT / "research/docs/agent_engineering_upgrade/real_llm_baseline/runs/20261104_02"
    config = json.loads((run / "experiment_config.json").read_text(encoding="utf-8"))
    results = json.loads((run / "results.json").read_text(encoding="utf-8"))
    requests = json.loads((run / "requests.json").read_text(encoding="utf-8"))
    cases = []
    for case in results["results"]:
        calls = [r for r in requests if r.get("case_id") == case["case_id"]]
        cases.append({"case_id": case["case_id"], "status": case["status"],
                      "requests": len(calls), "tokens": sum(r["usage"]["total_tokens"] for r in calls),
                      "reasons": case["reasons"],
                      "reference": case["case_id"] in config["reference_case_ids"]})
    truncated = [{"request_number": i + 1, "case_id": r["case_id"],
                  "max_tokens": r["max_tokens"], "usage": r["usage"],
                  "finish_reasons": r["finish_reasons"],
                  "node": "FaithfulnessChecker.check",
                  "node_attribution": "Source-chain inference: each five-call AGENT turn is intent256/router256/planner512/generate700/checker256; first two request hashes separately reconstructed. No raw prompt/answer archive exists, so checker hash cannot independently be reconstructed."}
                 for i, r in enumerate(requests) if r.get("model_json_object_valid") is False]
    immutable = {}
    for directory in (ROOT / "research/docs/agent_engineering_upgrade/evidence",
                      ROOT / "research/docs/agent_engineering_upgrade/real_llm_baseline"):
        for path in directory.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and ".tmp" not in path.parts:
                immutable[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in (ROOT / "eval/dataset").glob("*"):
        if path.is_file():
            immutable[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    value = {"source_baseline": "3c373ca502e2e08b4a343d751500c7ce77b28415",
             "model_status": "PARTIAL", "billed_p2_calls": 0, "cases": cases,
             "truncations": truncated, "immutable_artifact_sha256": immutable,
             "supplement_case_ids": [c["case_id"] for c in cases if c["status"] in {"ERROR", "NOT_RUN"}],
             "supplement_plan": {"status": "NOT_RUN_REQUIRES_EXPLICIT_COST_AUTHORIZATION",
                 "new_run_id": "p2_pre_memory_supplement_01_RESERVED_NOT_CREATED",
                 "checkout_commit": "3c373ca502e2e08b4a343d751500c7ce77b28415",
                 "concurrency": 1, "automatic_retries": 0, "http_attempt_cap": 40,
                 "total_token_cap": 30000, "estimated_requests": "12-25 plus one connectivity probe; hard stop40",
                 "estimated_total_tokens": "10000-20000; hard stop30000 incl probe; estimate from observed 9-case mean6475.7 tokens and5-10 calls/query case; security early exits may use less",
                 "monetary_cost": "UNKNOWN until current authorized account/model pricing is checked at execution; no fixed currency estimate fabricated",
                 "controls": "Original pre-P2 source, same frozen dataset/Gold, temp0, original per-node caps, fixed seed time and isolated SQLite; no new JSON/Memory changes in supplement"}}
    (OUT / "P2-A-analysis.json").write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"cases": len(cases), "reference_failures": sum(c["reference"] and c["status"] == "FAIL" for c in cases),
                      "truncations": len(truncated), "supplement_cases": len(value["supplement_case_ids"]),
                      "immutable_artifacts": len(immutable), "paid_calls": 0}))


if __name__ == "__main__":
    main()
