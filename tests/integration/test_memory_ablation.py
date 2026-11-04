from pathlib import Path


async def test_scripted_arm_exercises_node_prompts_with_no_paid_tokens():
    from eval.memory_ablation import run_arm
    from eval.multiturn import load_scenarios

    cases, digest = load_scenarios(Path("eval/dataset/agent_v2_extended.json"))
    case = next(c for c in cases if c.id == "context_loss")
    zero = await run_arm([case], digest, mode="M0", scripted=True)
    memory = await run_arm([case], digest, mode="M1", scripted=True)
    assert zero["results"][0]["status"] == "FAIL"
    assert memory["results"][0]["status"] == "PASS"
    assert memory["offline_generated_responses"] > 0
    assert memory["estimated_input_utf8_bound"] > 0
    assert memory["paid_api_calls"] == memory["paid_tokens"] == 0
