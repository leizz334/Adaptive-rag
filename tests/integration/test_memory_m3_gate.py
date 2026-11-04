from app.schemas.chat import ChatRequest
from eval.environment import BusinessEnvironment


async def test_public_m3_config_alone_has_no_cross_session_recall():
    async with BusinessEnvironment(memory_mode="M3") as env:
        async with env.container.session_factory() as db:
            state = await env.service._initial_state(
                db, ChatRequest(message="你好", user_id="u_demo"), "session-a", "test"
            )
        assert state.get("memory_preferences") == {}


async def test_server_injected_scope_recalls_only_matching_request_subject():
    from app.memory.long_term import MemoryIdentity, PreferenceMemory, verified_memory_scope

    store = PreferenceMemory()
    identity = MemoryIdentity("synthetic-tenant", "u_demo", verified=True)
    store.set_consent(identity, True, source="synthetic-consent")
    store.upsert(identity, "language", "en", source="prior-session:message1")
    async with BusinessEnvironment(memory_mode="M3") as env:
        env.service._memory_store = store
        with verified_memory_scope(identity):
            async with env.container.session_factory() as db:
                own = await env.service._initial_state(
                    db, ChatRequest(message="回答语言偏好", user_id="u_demo"), "fresh-own", "test"
                )
                other = await env.service._initial_state(
                    db, ChatRequest(message="回答语言偏好", user_id="other"), "fresh-other", "test"
                )
        assert own["memory_preferences"] == {"language": "en"}
        assert other["memory_preferences"] == {}


async def test_service_wide_identity_is_not_request_authentication():
    from app.memory.long_term import MemoryIdentity, PreferenceMemory

    store = PreferenceMemory()
    identity = MemoryIdentity("synthetic-tenant", "u_demo", verified=True)
    store.set_consent(identity, True, source="synthetic-consent")
    store.upsert(identity, "language", "en", source="old-session:1")
    async with BusinessEnvironment(memory_mode="M3") as env:
        env.service._memory_store = store
        env.service._memory_identity = identity
        async with env.container.session_factory() as db:
            state = await env.service._initial_state(
                db, ChatRequest(message="你好", user_id="u_demo"), "spoofed", "test"
            )
        assert state["memory_preferences"] == {}
