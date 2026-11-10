# P4-A1 initial real HTTP findings

Run20261110_A1_01executes41scenario tests through real Uvicorn/TCP, with35PASS/5FAIL/1BLOCKED. Raw requests include HTTP/SSE data, before/after SQLite snapshots, tool evidence and local graph spans. Preserve the run and original tests in Git; no paid model is involved. Trusted identity authentication is BLOCKED because user_id is a client assertion, not an authenticated principal. Claimed Owner/Session enforcement is tested separately.

| Failing scenario | First located cause | Classification / proposed correction |
| --- | --- | --- |
| refund_status | read_goals recognizes refund progress/records but not '退款状态'; generic status selects get_order, missing refund-status observation | Bounded application read-capability defect; add generic phrase with independent RED, retain original entity/permissions |
| compound_order_policy | search_knowledge succeeds but the controlled fixture renders only allowlisted business facts, omitting actual retrieved document evidence | Test-model fixture defect; support successful policy observations without Gold/case branches, preserve original FAIL |
| cancel_business_refusal | Planner proposes HITLbefore business write execution; test assumed shipped-order denial must occur before proposal | New-test contract issue to review; confirm proposal, then require actual service rule refusal and no mutation rather than treating proposal as a write |
| tool_failure | Injected get_order failure triggers mapped search_knowledge recovery; test wrongly requires every tool to fail | New-test contract issue to review; require failed primary read, no unsupported order fact/success claim and no mutation; allow evidenced recovery |
| sse_runtime_error | Runtime exception occurs after SSEheaders; stream ends without typed error/done while ordinary HTTPerror handling passes | APIerror contract defect; catch bounded errors inside route generator, retain cancellation semantics, never claim answer/action success |

Additional source-level actual contract risk: create_app(explicit_settings) configures routes but lifespan resolves global settings again. Establish RED before any change; explicit app settings must configure that app's container, including its isolated database.

Five initial failures are not all production bugs and cannot all be counted as application fixes. Test contract/fixture corrections will be versioned and disclosed, independently reviewed and will not alter any P0–P3Gold or original result. A2will use new Run IDs and retain all failed evidence. Initial A1pytest is failed, so its passes flag remains false until repaired matrix is revalidated.
