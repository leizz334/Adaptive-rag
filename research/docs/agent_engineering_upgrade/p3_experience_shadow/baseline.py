"""Verify historical raw evidence locally; no application or model execution."""

import json
import xml.etree.ElementTree as ET
from collections import Counter

from research.docs.agent_engineering_upgrade.p3_experience_shadow.manage import (
    BASE,
    HERE,
    ROOT,
    git,
    save,
    sha,
)


def read(path):
    return json.loads(path.read_bytes())


def main():
    assert git("rev-parse", "HEAD") == BASE
    remote = git(
        "ls-remote", "--heads", "origin", "refs/heads/codex/p2-answer-reliability"
    ).split()[0]
    assert remote == BASE
    old = HERE.parent / "p2_answer_reliability"
    aggregate = read(old / "evidence/s6_real_aggregate_v21.json")
    raw = []
    for name in ("20261105_S6_pairs_02", "20261108_S6_pairs_03"):
        raw.extend(read(old / f"runs/{name}/results.json")["groups"])
    assert len(raw) == 14
    candidate = [g for g in raw if g["variant"] == "R1"]
    assert len(candidate) == 7 and sum(g["status"] == "PASS" for g in candidate) == 6
    scored = [g for g in aggregate["groups"] if g["variant"] == "R1"]
    scores = [s for g in scored for s in g["answer_scores"]]
    assert sum(s["VERIFIED_GOAL_COVERAGE_LOWER_BOUND"] == 1 for s in scores) == 6
    assert Counter(s["ANSWER_FACTUAL_CORRECTNESS"] for s in scores) == {"NOT_ASSESSED": 7}
    assert Counter(s["ANSWER_FAITHFULNESS"] for s in scores) == {"NOT_ASSESSED": 7}
    assert Counter(s["OVERALL_TASK_SUCCESS"] for s in scores) == {"FAIL": 1, "NOT_ASSESSED": 6}
    old_requests = read(old / "runs/20261105_S6_pairs_02/requests.json")
    requests = read(old / "runs/20261108_S6_pairs_03/requests.json")
    assert requests[:11] == old_requests and len(requests) == 77
    assert sum(r["usage"]["total_tokens"] for r in requests) == 75467
    assert all(r["status"] == "RESPONSE" for r in requests)
    assert not any(
        r.get("model_error") for r in requests if ":R1:" in r["group"] and r.get("stage") == "judge"
    )
    datasets = {}
    for name, expected in (("original80", 80), ("old16", 13), ("holdout30", 22)):
        value = read(old / f"runs/s5_offline_fixedclock/S3/{name}/results.json")
        assert value["passed"] == expected
        datasets[name] = dict(passed=value["passed"], cases=value["cases"])
    suites = ET.parse(HERE / "evidence/a0_pytest.xml").getroot()
    total = sum(int(s.get("tests", 0)) for s in suites.iter("testsuite"))
    assert total == 475 and not any(
        int(s.get(k, 0)) for s in suites.iter("testsuite") for k in ("failures", "errors")
    )
    preservation = read(HERE / "evidence/preservation.json")
    assert all(sha(ROOT / p) == h for p, h in preservation["prior_files"].items())
    value = dict(
        status="PASS",
        baseline=BASE,
        verified_remote=remote,
        pytest=475,
        candidate_real_tool_state="6/7",
        required_fact_coverage="6/7",
        factual_correctness="7NOT_ASSESSED",
        faithfulness="7NOT_ASSESSED",
        overall="0PASS/1FAIL/6NOT_ASSESSED",
        candidate_judge_errors=0,
        old_datasets=datasets,
        historical_http=77,
        historical_tokens=75467,
        new_http=0,
        new_tokens=0,
        prior_files_frozen=len(preservation["prior_files"]),
        user_files_frozen=len(preservation["user_files"]),
        schema_design="separate experience metadata; no business migrations",
        active_enabled=False,
    )
    save(HERE / "evidence/a0_validation.json", value)
    print(json.dumps(value))


if __name__ == "__main__":
    main()
