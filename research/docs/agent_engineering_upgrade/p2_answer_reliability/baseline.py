"""Verify the delivered P2-R source/evidence rather than copying report claims."""

import json
import subprocess
import xml.etree.ElementTree as ET

from research.docs.agent_engineering_upgrade.p2_answer_reliability.manage import (
    BASE,
    HERE,
    ROOT,
    checkpoint,
    save,
)


def main():
    old = HERE.parent / "p2_agent_quality"
    metrics = json.loads((old / "evidence/r4_metrics.json").read_bytes())
    actual = {g: f"{m['passed']}/{m['cases']}" for g, m in metrics["groups"]["C3"].items()}
    assert {k: actual[k] for k in ("original80", "old16", "development", "blind")} == dict(
        original80="80/80", old16="13/16", development="27/30", blind="26/33"
    )
    real = json.loads((old / "runs/20261105_R5_pairs_01/analysis.json").read_bytes())
    final = real["arms"]["R1"]["all_complete_pairs"]
    assert final["passed"] == 7 and final["cases"] == 8
    assert real["arms"]["R0"]["all_complete_pairs"]["passed"] == 4
    ledger = json.loads((old / "runs/20261105_R5_pairs_01/requests.json").read_bytes())
    trunc = [r for r in ledger if r.get("model_error") == "truncated"]
    assert len(trunc) == 7 and sum(r["stage"] == "judge" for r in trunc) == 6
    assert not subprocess.check_output(
        ["git", "diff", "44f1031f651637fc96ef5f962f89018b9c1e9748", BASE, "--", "app"], cwd=ROOT
    ).strip()
    remote = subprocess.check_output(
        ["git", "ls-remote", "origin", "refs/heads/codex/p2-agent-quality"], cwd=ROOT, text=True
    ).split()[0]
    assert remote == BASE
    suites = list(ET.parse(HERE / "evidence/s0_pytest_valid.xml").iter("testsuite"))
    assert sum(int(s.attrib["tests"]) for s in suites) == 344
    assert all(int(s.attrib["errors"]) + int(s.attrib["failures"]) == 0 for s in suites)
    save(
        HERE / "evidence/s0_validation.json",
        dict(
            status="PASS",
            baseline=BASE,
            remote_head=remote,
            app_identical_to_freeze44=True,
            offline=actual,
            real=dict(
                R0="4/8",
                R1="7/8",
                selection=final["tool_selection"],
                arguments=final["tool_arguments"],
                environment=final["environment_success"],
            ),
            json_truncations=7,
            judge_truncations=6,
            pytest=344,
            initial_test_infrastructure_error="scratch parent absent;42setup errors/302passed;preserved originalXML,created parent,reran344passed",
            historical_pending="P2Q194/P2R109untouched",
            new_api_requests=0,
            source_manifest="preservation.json",
            truncated_requests=[
                dict(
                    group=r["group"], sequence=r["sequence"], stage=r["stage"], cap=r["max_tokens"]
                )
                for r in trunc
            ],
        ),
    )
    content = """# P2-S0 baseline

Verified actual origin/codex/p2-agent-quality HEAD e74f01db65fb9f3df929cdf5932919e1f10e453e. Its application tree is byte-identical in Git to source freeze44f1031f651637fc96ef5f962f89018b9c1e9748; later commits contain evidence/delivery metadata. Root workspace remains on prior P2-Q with user changes preserved. New branch codex/p2-answer-reliability lives in its own worktree.

Raw JSON revalidated: original80=80/80, old16=13/16, Development30=27/30, formerBlind33=26/33. Those datasets are now regression/development data. Actual real completed pairs R0=4/8,R1=7/8, R1 tool selection91.67%,arguments90.91%,environment8/8. These are tool/trajectory/state scores, never semantic answer scores. Seven raw truncations include six Judge and one Planner at512. Exact request IDs/caps are in s0_validation.json. Uncertain historical request109 and P2-Q194 remain untouched.

Fresh344pytest pass with no production/source changes. Initial run had42setup errors because scratch parent was absent (302passed); original failure XML retained, directory created and full344verified. This was test infrastructure, not an Agent regression. Historical reports/state/source/Prompt/eval/data/experiment files have raw SHA256 inventories in preservation.json. Old task namespace and progress prefix are not rewritten.

Observed source path: DeepSeekProvider rejects structured finish_reason=length before parser. FaithfulnessChecker asks for duplicated status+supported, free-length spans/rationale and512 cap; broad errors erase detail. Judge error selects _offline_answer; that function assumes offline configuration, returns one latest tool fact or first arbitrary chunk. Thus real B31 falsely claims no configured model and quotes unrelated policy; dv06 loses one goal despite both tool results. No evidence proves token increase alone solves this. S1 will compact/validate schema, preserve error classification and implement safe fact/limitation fallback with no extra call.

No new paid request. P3/P4 not started.
"""
    (HERE / "P2-S0_BASELINE.md").write_bytes(content.encode())
    checkpoint(
        "P2-S0",
        [
            "P2-S0_BASELINE.md",
            "evidence/s0_validation.json",
            "evidence/preservation.json",
            "evidence/s0_pytest_valid.xml",
        ],
        "344pytest;actualremote/source/rawmetricsverified",
        "S1RED/GREEN Judge and groundedfallback",
    )
    print("S0 verified344tests;baseline/rawmetrics/source/remote;0newAPI")


if __name__ == "__main__":
    main()
