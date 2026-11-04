# P2 selective Context Builder

M1: after get_or_create validates session owner, ChatService loads recent messages and builds a separate resolved_query. Original user_query is unchanged for guardrails, write-intent authorization, confirmation and persistence. Server-confirmed actions bypass inference from remembered targets.

Entity precedence: current explicit user target, then most recent safe user message in the bounded window, then (M2) validated summary entity. Assistant text, injection turns and arbitrary summary prose cannot establish an order reference. Multiple/absent targets require clarification without tool calls. Memory carries identifiers only; tools still enforce ownership and query current business state.

Intent/Router use the small resolved query; Planner receives the selected reference only; Generate receives a labelled bounded untrusted user-history block. No full transcript is copied into every node. Existing planner/Gold/scorers remain unchanged.

P1 BusinessEnvironment explicitly defaults M0 so original frozen P1 scenario expectations remain reproducible after adding production Memory. Opt-in memory_mode is a test-fixture adaptation, not a changed Gold or success criterion.

B verification: original seven reference cases7/7 pass using OfflineLLMProvider and unchanged P1 driver/score_tools/score_goal, including changed-state fresh reads; M0 original tests still assert prior context failure. Cross-user session/foreign order/ambiguity/current target/assistant-injection and real-shaped generation prompt tests pass. Full229tests passed. This is OFFLINE_ENGINEERING evidence, real Memory quality remains NOT_RUN.
