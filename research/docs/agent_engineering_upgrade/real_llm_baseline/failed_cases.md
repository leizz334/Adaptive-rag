# Failures and unrun cases

No evaluated scenario failed because **no scenario was run**. All selected cases retain their original Gold and are NOT_RUN due to failed connectivity.

Actual failed checks:

1. Local sandbox network permission failure: LLMProviderError → ConnectError → OSError → PermissionError (errno 13, WinError 5). No gateway HTTP response. Infrastructure error.
2. Explicitly elevated read-only connectivity probe: gateway HTTP 200 → JSONDecodeError (with StopIteration context). No valid completion, response-reported model or usage. Gateway/API protocol error, not a measured model reasoning failure. Raw response body was not retained; do not assume HTML or a particular upstream error page.

| Selected case ID | Role | Status |
|---|---|---|
| context_loss | Historical reference failure | NOT_RUN |
| freshness_ORD10001_pronoun_stable | Historical reference failure | NOT_RUN |
| freshness_ORD10001_pronoun_changed | Historical reference failure | NOT_RUN |
| freshness_ORD10002_pronoun_stable | Historical reference failure | NOT_RUN |
| freshness_ORD10002_pronoun_changed | Historical reference failure | NOT_RUN |
| freshness_ORD10003_pronoun_stable | Historical reference failure | NOT_RUN |
| freshness_ORD10003_pronoun_changed | Historical reference failure | NOT_RUN |
| order_lookup | Single-turn query | NOT_RUN |
| explicit_target_change | Multi-turn explicit query | NOT_RUN |
| greeting | Direct response | NOT_RUN |
| argument_binding | Confirmation argument binding | NOT_RUN |
| cancel_pending | Approval constraint | NOT_RUN |
| foreign_order | Ownership constraint | NOT_RUN |
| cross_user_session | Session permission constraint | NOT_RUN |
| injection | Safety refusal | NOT_RUN |

No failure was relabelled as a pass and no offline response was used as a substitute. API timeouts: none observed. Scenario refusals, tool execution failures, safety and model quality: not assessed. Resolve the gateway response compatibility issue and authorize a separate new run before continuing; no P2.
