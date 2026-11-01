from eval.runner import _resume_bullets


def test_unavailable_judge_report_formats_not_run_instead_of_crashing():
    empty = {"faithfulness": None, "hallucination_rate": None}
    bullets = _resume_bullets(
        {
            "generation": {
                "naive_no_context": empty,
                "rag": empty,
                "rag_plus_self_check": empty,
                "hallucination_relative_drop": None,
            }
        }
    )
    assert len(bullets) == 2
    assert all("N/A" in b for b in bullets)
    assert "0%" not in " ".join(bullets)
