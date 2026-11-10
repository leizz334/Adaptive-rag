"""Required-auth synthetic runtime using the real production verifier and routes."""

import hashlib
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from pydantic import SecretStr

from app.config.settings import Settings
from research.docs.agent_engineering_upgrade.p4_api_e2e import worker as fixture
from research.docs.agent_engineering_upgrade.p4_dependency_integration.manage import HERE, save, sha

# Public, deliberately non-production fixtures. No generated/private token is committed.
TOKENS = {
    "user": "a" * 43,
    "other": "b" * 43,
    "admin": "d" * 43,
    "expired": "e" * 43,
    "revoked": "f" * 43,
}


def credential_fixture():
    now = datetime.now(UTC)
    entries = []
    for kind, token in TOKENS.items():
        entries.append(
            dict(
                token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                subject="u_other"
                if kind == "other"
                else "u_admin"
                if kind == "admin"
                else "u_demo",
                roles=["admin"] if kind == "admin" else ["user"],
                expires_at=(
                    now + timedelta(hours=2) if kind != "expired" else now - timedelta(minutes=1)
                ).isoformat(),
                revoked=kind == "revoked",
            )
        )
    return json.dumps(dict(version=1, credentials=entries))


def main():
    original_settings = fixture.isolated_settings
    original_factory = fixture.create_worker

    def required_settings(directory):
        data = original_settings(directory).model_dump()
        data.update(auth_mode="required", auth_credentials=SecretStr(credential_fixture()))
        return Settings.model_validate(data)

    def factory(directory, stop_token, holder):
        app = original_factory(directory, stop_token, holder)
        original_lifespan = app.router.lifespan_context

        @asynccontextmanager
        async def lifespan(application):
            async with original_lifespan(application):
                path = directory / "startup.json"
                data = json.loads(path.read_bytes())
                data.update(
                    auth_mode=application.state.settings.auth_mode,
                    authentication="production_opaque_digest_verifier",
                    legacy_auth=False,
                    credential_fixture="public synthetic test tokens only",
                    fixture_dependency_sha256=sha(fixture.__file__),
                )
                save(path, data)
                yield

        app.router.lifespan_context = lifespan
        return app

    fixture.HERE = HERE
    fixture.isolated_settings = required_settings
    fixture.create_worker = factory
    fixture.main()


if __name__ == "__main__":
    main()
