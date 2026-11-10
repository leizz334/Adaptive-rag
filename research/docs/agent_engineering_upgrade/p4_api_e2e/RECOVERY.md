# P4-A recovery

Existing worktree D:/Code/Adaptive-rag/.worktrees/p3-experience-validation now uses codex/p4-api-e2e from verified586d0e01381d69bdc1653e5563e3ce48e9b82219. No new worktree/stash/reset. Original edited review CSV SHA2569ae24fe60c2d75498a4429cf79e03f5a0f3955380cd51d6064fec0fa51ad5aa7must remain unchanged and unstaged. Read AGENTS/registry/progress, actual Git and evidence before resuming. Do not rerun Initializer or paid historical experiments.

## Architecture decisions (preserve verbatim)

Real Uvicorn child plus real TCP HTTPX client; private on-disk SQLite and synthetic seed; actual FastAPI/routes/Session/M2/Graph/retrieval/tools/Generate/Judge; only LLM is explicitly controlled. Local trace/tool/state instrumentation is separate from business behavior. No outbound paid API, external tracing or production dependency. No Experience Active. No client user_id is a trusted identity; authenticated cross-user security is BLOCKED if no trust boundary exists. Do not retrofit an authentication system in this E2E phase.

Per-task acceptance/test/state/commit A0→A1→A2, then normalpush/lsremote and STOP. Preserve initial HTTP/SSE failures; fix evidenced bugs RED→GREEN only. Only stop owned child PID; never broad-stop Uvicorn/Python or other user services. Later P4-B/C/D/E are not authorized.

A0PASS:realUvicornrun20261110_A0_02PID27064/127.0.0.1:64840,4HTTPrequests/privateSQLite/ControlledLLM/M2/localtrace/seedverified,ownedPIDgracefulstop. InitialA0_01infraWindowsloopbacksocketguardfailedpreAPI;source/logretained,loopback-onlyfixRED/GREEN. A0unit4PASS. Noappchanges;providerfakeexplicit/noDeepSeek/outboundremote. NextA1realHTTPmatrixandfailureevidence,thenA2RED/GREENminimalfix/fullregression. PreserveuserCSVunstaged.

A1initialrun20261110_A1_01=41scenarios35PASS5FAIL1BLOCKED(trustedauthnotimplemented);passesfalse. Fivefailures:refundgoalphraseapplication;policyfixtureomission;cancel-before-HITLassumption;toolrecoveryassumption;SSEruntimeincompleteerrorending. Initialevidencecommittedbeforefix. A2dependsverifiedA0+recordedA1failures so repairdoesnotcircularlyrequireA1PASS. Independentreviewp4_independent_reviewassessingclassifications. NeedRED/GREENminimalrefund/lifespan/SSEfix;fixture/testcontractcorrectionsdisclosed;newrunIDs/fullregression;preserveoriginaluserCSV.

A2FIXESVERIFIED:app/main explicitSettingslifetime,app/agents/goals refundstatusphrase,app/api/routes/chat lateSSEerror/done;5REDthenGREEN. Harnessloopback/policyexcerpt/capturefailopenfixed;captureRED/GREEN. Canceltestnowactualconfirmedbusinessdenial+failedcancelmetadata,toolrecoveryallowlistssearch_knowledge/noinventedfacts;2contractcorrectionsnotapplicationfixes. RealrunA2_01=41PASS1BLOCKED;full670PASS1authBLOCKED;stricterfinalrunA2_final_01=42total41PASS0FAIL1BLOCKED/55HTTP/owned20660stoppedgracefully/sourcehashunchanged. Legacy2140regressions. Nextsourcefixcommit,A1revalidationcommit,finalaudit/report+statecommit,push/verify/STOP. NoNewWorktree/paid/Active/P4B.
