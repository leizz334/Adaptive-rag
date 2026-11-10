# P4-A1 real HTTP revalidation

Source repair checkpoint9abc63c8a157811ea964b5a4bfdb8f08b71622f3is validated by final run20261110_A2_final_01:42scenarios,41PASS,0FAIL,1BLOCKED;55recorded API requests, real Uvicorn PID20660gracefully stopped, source hashes unchanged during execution. Startup/control requests are separate lifecycle traffic, not extra passes.

Original41scenario run35PASS/5FAIL/1BLOCKEDremains in initial evidence commit56cca47596db5c9679a99abde4be8cb4ca98a509. The final42includes one additional trace-capture failure isolation control. Two original test assumptions were corrected after source/evidence review: confirm an ineligible write before checking its business refusal; permit legitimate policy fallback while rejecting invented order facts. These are not application improvements or historical Gold changes. Three production and three harness fixes are separately described in P4-A2_FIXES.md.

Available health/ready/capabilities/admin/validation paths, business reads, multi-turn M2and summary restoration, actual RAGdocument delivery, compound evidence, Owner/Sessionchecks under declared identity, confirmation/idempotency, faults, SSEsuccess/error and real client disconnect all pass their final assertions. For the deliberate trace-sink error, evidence absence is explicit rather than reported as a complete trace.

Trusted identity authentication/anti-impersonation remains **BLOCKED**, not PASS. Client-controlled user_idcannot prove login identity. The phase does not implement a new auth subsystem or claim secure production cross-user sharing. Real DeepSeek and external-dependency semantics are NOT_RUNby authorized scope. A1evidence is complete with this explicit capability blocker; overall phase remains PARTIAL_PASS.
