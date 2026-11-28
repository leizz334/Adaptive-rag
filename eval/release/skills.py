"""Verify recorded progressive Skill loading against its paired control."""

import json

from eval.release.shared.budget import MODEL, RunStopped, metered_usage

PRELOAD_SEPARATOR = "\n\n本对照组预加载的技能指令\n\n"


def prompt_tokens(receipt):
    usage = metered_usage(receipt["response"])
    if (
        receipt["http_status"] != 200
        or not usage
        or usage != receipt["usage"]
        or receipt["request"]["model"] != MODEL
        or receipt["request"]["thinking"] != {"type": "disabled"}
    ):
        raise RunStopped(f"Unverifiable Skill receipt {receipt['id']}")
    return usage["prompt_tokens"]


def verify(folder):
    manifest = json.loads((folder / "manifest.json").read_bytes())
    pairs = [json.loads(line) for line in (folder / "preload.jsonl").read_bytes().splitlines()]
    receipts = json.loads((folder / "requests.json").read_bytes())
    receipt_by_id = {receipt["id"]: receipt for receipt in receipts}
    linked = {
        pair[field] for pair in pairs for field in ("baseline_request_id", "preloaded_request_id")
    }
    if (
        not pairs
        or [pair["case"] for pair in pairs] != manifest["case_order"]
        or not len(receipts) == len(linked) == 2 * len(pairs)
        or linked != receipt_by_id.keys()
        or manifest["model"] != MODEL
        or manifest["thinking_enabled"]
    ):
        raise RunStopped("Unexpected Skill replay inputs")

    progressive_tokens = 0
    preloaded_tokens = 0
    for pair in pairs:
        baseline = receipt_by_id[pair["baseline_request_id"]]
        control = receipt_by_id[pair["preloaded_request_id"]]
        before, after = dict(baseline["request"]), dict(control["request"])
        baseline_messages, control_messages = before.pop("messages"), after.pop("messages")
        original, extra, body = control_messages[0]["content"].partition(PRELOAD_SEPARATOR)
        case = pair["case"]
        if (
            before != after
            or baseline_messages[1:] != control_messages[1:]
            or baseline_messages[0] != {**control_messages[0], "content": original}
            or not extra
            or len((extra + body).encode("utf-8")) != pair["added_utf8_bytes"]
            or any(f"## {name}\n" not in body for name in pair["instruction_files"])
            or baseline["scope"]["job"] != f"B/{case}/1"
            or baseline["scope"]["stage"] != "intent"
            or control["scope"]["job"] != f"preload/{case}/1"
            or control["scope"]["stage"] != "intent_preload"
            or pair["output_error"] is not None
        ):
            raise RunStopped(f"Skill requests are not paired for {case}")
        baseline_usage, control_usage = prompt_tokens(baseline), prompt_tokens(control)
        if (
            baseline_usage != pair["prompt_tokens_progressive"]
            or control_usage != pair["prompt_tokens_preloaded"]
        ):
            raise RunStopped(f"Recorded Skill prompt usage differs for {case}")
        progressive_tokens += baseline_usage
        preloaded_tokens += control_usage

    print(
        json.dumps(
            {
                "suite": "skills",
                "verified": True,
                "pairs": len(pairs),
                "requests": len(receipts),
                "progressive_prompt_tokens": progressive_tokens,
                "preloaded_prompt_tokens": preloaded_tokens,
                "prompt_token_reduction": 1 - progressive_tokens / preloaded_tokens,
            }
        )
    )
