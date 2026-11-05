# P2-S0 baseline

Verified actual origin/codex/p2-agent-quality HEAD e74f01db65fb9f3df929cdf5932919e1f10e453e. Its application tree is byte-identical in Git to source freeze44f1031f651637fc96ef5f962f89018b9c1e9748; later commits contain evidence/delivery metadata. Root workspace remains on prior P2-Q with user changes preserved. New branch codex/p2-answer-reliability lives in its own worktree.

Raw JSON revalidated: original80=80/80, old16=13/16, Development30=27/30, formerBlind33=26/33. Those datasets are now regression/development data. Actual real completed pairs R0=4/8,R1=7/8, R1 tool selection91.67%,arguments90.91%,environment8/8. These are tool/trajectory/state scores, never semantic answer scores. Seven raw truncations include six Judge and one Planner at512. Exact request IDs/caps are in s0_validation.json. Uncertain historical request109 and P2-Q194 remain untouched.

Fresh344pytest pass with no production/source changes. Initial run had42setup errors because scratch parent was absent (302passed); original failure XML retained, directory created and full344verified. This was test infrastructure, not an Agent regression. Historical reports/state/source/Prompt/eval/data/experiment files have raw SHA256 inventories in preservation.json. Old task namespace and progress prefix are not rewritten.

Observed source path: DeepSeekProvider rejects structured finish_reason=length before parser. FaithfulnessChecker asks for duplicated status+supported, free-length spans/rationale and512 cap; broad errors erase detail. Judge error selects _offline_answer; that function assumes offline configuration, returns one latest tool fact or first arbitrary chunk. Thus real B31 falsely claims no configured model and quotes unrelated policy; dv06 loses one goal despite both tool results. No evidence proves token increase alone solves this. S1 will compact/validate schema, preserve error classification and implement safe fact/limitation fallback with no extra call.

No new paid request. P3/P4 not started.
