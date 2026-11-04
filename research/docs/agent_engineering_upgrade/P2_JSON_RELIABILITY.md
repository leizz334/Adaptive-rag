# Independent JSON reliability repair (P2-A)

This is a reliability change, not a Memory improvement. Real model reruns: NOT_RUN, new paid tokens0.

Four original malformed256-token outputs followed generation in the AGENT chain and ended finish_reason=length. Provider now preserves response model/finish_reason and rejects truncated structured JSON (even syntactically complete prefixes) with non-retryable LLMTruncationError. This prevents a hidden3-attempt transport retry or unsafe partial plan. FaithfulnessChecker classifies that as INVALID_OUTPUT; network failures stay JUDGE_ERROR, never fabricated hallucination/Memory gains.

Judge output allowance is explicit: LLM_JUDGE_MAX_TOKENS defaults512, constrained256..2048, wired through build_graph. Other node caps and prompts are unchanged. One judge call only; no automatic extended-budget retry. 512 cannot guarantee no future truncation; actual truncation rate after repair is NOT_RUN.

RED:5failed/1passed (truncation accepted, response model discarded, invalid output misclassified and old256judge allowance). Intermediate GREEN exposed retryable base exception (2fail/8pass); introduced a specific non-retryable truncation error. Final targeted run20passed (new reliability, original judge and tracing regressions). Evidence: p2_evidence/P2-A-pytest.xml. No real HTTP requests; only MockTransport/fixture models.

The Memory ablation holds this repair constant in all arms and separately records the reliability-only M0 arm. No comparison of original real2/9 against an offline Memory score is a causal improvement claim.
