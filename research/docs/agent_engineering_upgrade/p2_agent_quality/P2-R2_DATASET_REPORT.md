# P2-R2 Chinese development / blind data

Development: **30 tasks / 52 turns**, deliberately varied goals rather than ID/amount variants. Explicit headers/amount/payment, transport history, shipment-only/mixed evidence, line items, recent/elliptic/long-window references, joint targets and ambiguity, explicit target change/earlier target, policy topic switch, live state events, eligibility versus action, pending/confirmed/invalid/cross-session confirmation, Owner isolation, no-tool social tasks, missing/nonexistent target, warehouse events, confirmation-time business rejection and repeated-confirmation idempotency. No model output or candidate behavior was used to author Gold. Development is available for analysis and code iteration.

Blind: **33 tasks / 54 Chinese turns**, independently authored from public schema/tool/seed contracts without ContextBuilder/Planner inspection or runtime execution. Inputs/Gold/per-case results are withheld from the implementer until a candidate source/Prompt freeze. The separate author reported no overlap with prior frozen datasets. This isolation is process-based, not an inaccessible storage enclave; scripts necessarily parse data for aggregate quality checks. No claim of cryptographic blinding or statistical population sampling.

| Artifact | SHA256 |
|---|---|
| Development | `634317b75ed575321c66feed9e8b6347d70ca2b9a03208493f62797c812e7bb4` |
| Blind holdout | `4b20f92f24d53afeafea4c6375e5da3edab04a75ee48fa31c1272448dbc5b275` |

Schema agent-scenarios-v2.1, strict UTF8, no U+FFFD or punctuation-only replacement corruption. IDs and entity-normalized full task sequences are unique across the split. Exact shared turn phrases:0; entity-normalized scenario overlap:0. Known fixture order/status/mutation/confirmation constraints checked statically. Initial database always comes from fresh synthetic seed; no real order/write endpoint is used.

Policy retrieval may legitimately follow RAG without a registered tool event; new policy Gold permits that alternative instead of forcing search_knowledge. Actual shipment-event goals require track_shipment, which validates ownership internally; header-only goals require get_order without unnecessary tracking. Mixed goals require both. More than one legitimate path is allowed through appropriate optional tools/maxima rather than a single hardcoded order. Original old16/80 Gold remains untouched, including disputed legacy search_knowledge requirements.

Limitations: the standard frozen scenario driver cannot inject transient tool/network failures or controlled assistant-only histories, so independent runtime unit/integration tests cover fault recovery and assistant exclusion. The Goal Oracle checks tools/state/observations, not semantic truth of final answers; passing a permissive policy trajectory does not prove answer quality. Real model answers and errors will be retained for inspection. No labels will be changed after evaluation, and failed blind tasks will not drive the same candidate version's tuning.

R5 predeclares representative Development selection plus six Blind cases chosen by SHA256(seed+caseID) after source freeze, independent of outcomes, with whole-pair budget forecasts. All33Blind tasks run offline after the freeze; real budget may cover only a stated subset. Any repeated pair must use a separate durable request namespace and remain inside420HTTP/420ktoken bounds.

