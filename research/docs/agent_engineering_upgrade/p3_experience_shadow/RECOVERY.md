# P3-A recovery

Authorized A0–A6 continuously; never reinitialize. Baseline70d65e36687ae31133b08aec065f0a3ca4a6b848 verified local and remote, previous P2-S clean. New worktree D:/Code/Adaptive-rag/.worktrees/p3-experience-shadow, branch codex/p3-experience-shadow. Root user changes preserved. Conda adaptive-rag. Read plan, task registry/progress and Git before resuming.

## Architecture decisions (preserve verbatim)

Experience processing is an isolated offline completed-trace runner. No production hook, experience retrieval, prompt injection or business execution is introduced. Default mode off; shadow explicit; active rejected. Use existing SQLAlchemy async engine/session infrastructure with a separate explicit experience metadata base so application startup/business schema are unchanged. All repository operations require scoped offline identity; no production cross-user or cross-session sharing. VERIFIED_OFFLINE is test evidence, not human approval or ACTIVE readiness. Unknown semantic claims stay NOT_ASSESSED; model-assisted review is never called human annotation.

New budget120HTTP/120000tokens/estimatedUS$2; no new calls yet. Saved P2-S77HTTP/75467tokens are historical and must never be replayed for billing. Old P2-Q/P2-R uncertain journals are untouched. Prefer deterministic candidate templates and independent saved-answer review; zero new calls is valid if sufficient for bounded engineering verification.

Current A0: fresh475baseline running scratch/p3a-baseline-01. Independent child p3_semantic_review owns only A1 semantic_review directory/report, no paid calls. p3_trace_diagnosis owns only A2 evidence/report, no app changes. Parent owns app/tests/state/commits. No product Multi-Agent. Next: verify A0, register phase exactly once, commit baseline, then A1 review evidence.

A0=e0a8fec fresh475;A1=0ba21ed modelassisted14answers/R1=4P1F2U humanNOT_RUN;A2=da5060b taxonomy14tests/20reviewedassessments. A3core34tests and full516PASS/Mypy146. Ruling: adding field toexistingSettings violated historicalfreeze;restoredfileexactly andnewindependentExperienceSettings;firstfailureXMLretained. Alloldapp/eval unchanged. A3newcontextnormalization separate fromA2artifact. E2independent32case dataset frozen byauthor hash e4359ee34c69f8874b9fe91c8fa5e116b0ea39802efac903be5ca70797225cff, parent hasNOTreadconcretelabels beforematcherfreeze. NextA4storage. NewHTTP0.

A3=0f3dca9;A4=e731553 full533PASS. A5newmatcher10REDthenGREEN; explicitshadowclockREDthenfixed; independentreview3importantfindings/4RED:deleteCAS,validationrefprivacy,strictJSONpointer. Onefixpass66coreGREEN/Mypy148. Freeze before E2data; parenthasNOTread32concretecases yet. App/evaloldfilesunchanged; onlynewapp/experience. E0/E1developmentpreflight exact5Mockresponses noHTTP. Nextnewruns/p3a_shadow_01; do notoverwriteoldruns. New paidHTTP0.
