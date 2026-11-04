# M3 isolated preference prototype

M3 is not enabled for real users. The production container injects neither a preference store nor verified request identity. MEMORY_MODE=M3 or client user_id alone cannot activate recall; the current API does not authenticate identities.

The in-memory store allows only enumerated language/tone/response_style preferences, never order state, balances, approvals, free-form instructions or personal profiles. Records have tenant/subject/key, bounded provenance, version, update time, expiry and validity. Explicit provenance-bearing consent is required; optimistic version conflicts reject stale updates; invalidate/expiry remove results from recall; delete/revoke discard stored values. No vector index/cache/backups or durable external service exists in this prototype.

Trusted server/test code must inject a task-local verified_memory_scope per request. A service-wide identity attribute is not authentication and is ignored. Subject must match the request, while tenant/verified assertion comes from the server scope, never request fields. ContextVar scope resets in finally and is independently tested across concurrent tasks. This interface is an assertion boundary for a future real authenticator, not an implementation of one; do not wire it to public client identity.

Only Generate receives selected enum preferences as labelled data; they cannot affect tool parameters, permissions or approvals. Offline M3 ablations use synthetic consented test principals explicitly; real M3 effects are NOT_RUN. Same-session M2 remains available when M3 is disabled.

D tests:5original RED failures, lifecycle/update/expiry/delete/tenant/user isolation GREEN; a service-wide identity regression reproduced RED and fixed with per-request ContextVar scope, including task reset tests. Earlier full241 regression passed; final phase regression includes the scope hardening. No paid calls or production data.
