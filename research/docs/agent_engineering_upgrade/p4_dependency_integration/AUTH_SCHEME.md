# Server-provisioned credential authentication

Required authentication is the default for development/production and for testing unless explicitly overridden. Public /health,/ready,/capabilitiesand metrics retain their existing non-business behavior. Both /chatand /chat/streamauthenticate before business dispatch; /adminrequires the server-provisioned admin role. Missing/invalid/expired/revoked credentials return401; conflicting client identity or insufficient role returns403. No header/client claim can grant a different subject/role.

The small deployment scheme uses32cryptographically random bytes in an opaque URL-safe Bearer token, out-of-band operator provisioning, SHA256digest-only registry entries, UTCexpiry/not-before and revocation. It is genuine server credential verification, not a test principal injector or an OAuth/JWTimplementation. It does not prove a human/federated identity or provide account-registration/password/OIDCservices. Operators must establish subject ownership before provisioning and deploy TLS; credential possession grants that subject's access. Keep raw tokens and registry/private configuration out of Git/logs/trace payloads. The registry is bounded to256entries/128KB, rejects duplicate keys/digests/unknown roles/fields and never reports secret contents in parse errors.

## Provisioning and migration

Use a trusted local operator shell; the command prints a new raw token once. Do not paste its output into chat, commit it, or enable shell transcript capture. Choose a future UTCexpiry and an existing application subject. Only explicitly authorized operators may provision admin role.

```text
python -m app.core.auth --subject YOUR_ACCOUNT_ID --expires-at FUTURE_UTC_ISO_TIMESTAMP
# Optional --admin is an operator-only provisioning decision, not a client role claim.
```

Store only registry_entryvalues in AUTH_CREDENTIALS, a secret-managed JSONstring:

```json
{"version":1,"credentials":[{"token_sha256":"64_lowercase_hex_digest_from_provisioner","subject":"YOUR_ACCOUNT_ID","roles":["user"],"expires_at":"FUTURE_UTC_ISO_TIMESTAMP","revoked":false}]}
```

Clients send `Authorization: Bearer <privately delivered token>`. Existing JSONbody/response shapes remain. A matching user_idis accepted; omitted/default anonymousis replaced with the verified subject; a different user_idis rejected. Bearer tokens never enter ChatRequest, model prompts, session messages or tool arguments. Owner/Sessionchecks, required confirmation, idempotency and M2continue to use the bound subject. Admin role does not override ownership or confirmation. Authentication does not automatically enable M3/experience sharing or Active.

Update/revoke/rotate registry entries through trusted configuration and restart all processes. Expiry/not-before are checked each request even without restart. Rotation can provision a second digest for the same subject then revoke the old entry. No unauthenticated HTTPissuer, hot configuration mutation or private user-directory synchronization is added. Empty required registry leaves business routes fail-closed; health can still report infrastructure readiness. HTTPS, operator secret delivery and deployment access controls are operational prerequisites, not certified by local tests.

## Explicit historical fixture compatibility

AUTH_MODE=legacy_testis permitted only with APP_ENV=testing. Production/development startup rejects it. It is deliberately unauthenticated and must never be labeled trusted auth. The old TestClienthelper and old P4-Acontrolled worker opt in explicitly to retain old regression behavior; no historical P4-Aresult or authentication BLOCKEDrecord is rewritten. New P4-BHTTPtests explicitly set requiredand register synthetic credentials in the real production verifier. Do not set legacy_testin deployed Compose/APIenvironments.

The standalone x-admin-tokenmechanism remains only in that explicit legacy test app. In requiredmode, an admin Bearer role is necessary and an old x-admin-tokencannot bypass it. Default application configuration remains secure even when tests are installed.

## Windows evidence and limits

19initial auth REDcases precede implementation;19unit cases plus5old APIfixture cases pass. Independent review adds33passing verifier/route counterexamples. Separate actual TCP/Uvicornmatrix20261110_B0_auth_01has20PASS/0FAILusing private SQLite and a controlled model. No principal is monkeypatched in this matrix. Test credentials are deliberately public synthetic fixtures, not production credentials; possession verification/identity binding uses the same application implementation as deployment.

PostgreSQL/Redis/Qdrant, multi-process confirmations and restart recovery remain untested until Ubuntu B2/B3. A process-local confirmation registry is a known readiness risk; no distributed HITLclaim follows from authentication tests. No paid DeepSeek, production user database or Experience Active is used.
