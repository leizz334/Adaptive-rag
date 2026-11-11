"""Two production-settings actual-ASGI workers, two authenticated synthetic owners."""

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from research.docs.agent_engineering_upgrade.p4_security_remediation.runtime import Runtime

pytestmark = pytest.mark.skipif(
    os.environ.get("P4B_RUN_LIVE") != "1", reason="owned real services required"
)


@pytest.fixture(scope="module")
def api():
    run = Runtime()
    try:
        run.start()
        yield run
    finally:
        run.stop()


def put(api, identifier, text, subject="user", method="POST", expected=200):
    return api.request(
        method,
        "/knowledge/documents/" + identifier,
        {"title": "合成退货政策", "content": text},
        subject=subject,
        expected=expected,
    )


def query(api, subject="user", mode="hybrid", worker=0):
    return api.request(
        "POST",
        "/knowledge/search",
        {"query": "退货政策合成退款条件", "mode": mode},
        subject=subject,
        worker=worker,
        expected=200,
    ).json()


def test_private_schema_rejects_client_scope_and_requires_auth(api):
    api.request("POST", "/knowledge/search", {"query": "政策"}, subject=None, expected=401)
    for key in ["tenant_id", "user_id"]:
        api.request("POST", "/knowledge/search", {"query": "政策", key: "u_other"}, expected=422)
        api.request(
            "POST",
            "/knowledge/documents/forged",
            {"title": "policy", "content": "synthetic", key: "u_other"},
            expected=422,
        )
    api.request("POST", "/chat", {"message": "退货政策", "user_id": "u_other"}, expected=403)


def test_same_ids_bm25_dense_hybrid_rerank_cache_and_citations(api):
    put(api, "shared_id", "退货政策合成退款条件：TENANT_A_ONLY，期限31天。")
    put(api, "shared_id", "退货政策合成退款条件：TENANT_B_ONLY，期限47天。", "other")
    for mode in ["bm25", "dense", "hybrid"]:
        for worker in [0, 1]:
            for subject, yes, no in [
                ("user", "TENANT_A_ONLY", "TENANT_B_ONLY"),
                ("other", "TENANT_B_ONLY", "TENANT_A_ONLY"),
            ]:
                for _ in range(2):
                    data = query(api, subject, mode, worker)
                    assert data["chunks"] and data["citations"]
                    assert yes in json.dumps(data) and no not in json.dumps(data)
                    expected = api.subjects[subject]
                    assert all(c["metadata"]["tenant_subject"] == expected for c in data["chunks"])
                    assert {c["chunk_id"] for c in data["citations"]} <= {
                        c["chunk_id"] for c in data["chunks"]
                    }


def test_cross_owner_update_delete_and_forged_headers(api):
    put(api, "only_a", "退货政策合成退款条件 OWNER_A_SECRET")
    put(api, "only_a", "stolen", subject="other", method="PUT", expected=404)
    api.request("DELETE", "/knowledge/documents/only_a", subject="other", expected=404)
    row = api.request(
        "POST",
        "/knowledge/search",
        {"query": "OWNER_A_SECRET"},
        subject="other",
        headers={"x-user-id": "u_demo", "x-tenant-id": "u_demo"},
        expected=200,
    )
    assert "OWNER_A_SECRET" not in row.text


def test_updates_deletes_reindex_cross_worker_and_no_public_fallback(api):
    put(api, "changing", "退货政策合成退款条件 OLD_A_REVISION")
    query(api)
    put(api, "changing", "退货政策合成退款条件 NEW_A_REVISION", method="PUT")
    assert "OLD_A_REVISION" not in json.dumps(query(api, worker=1))
    api.request("POST", "/knowledge/reindex", expected=200, worker=1)
    assert "NEW_A_REVISION" in json.dumps(query(api))
    api.request("DELETE", "/knowledge/documents/changing", expected=200, worker=1)
    assert "NEW_A_REVISION" not in json.dumps(query(api))
    api.request("POST", "/knowledge/reindex", subject="other", expected=200)
    assert "TENANT_A_ONLY" not in json.dumps(query(api, "other"))


def test_chat_and_sse_use_scoped_graph_and_final_citations(api):
    for subject, excluded in [("user", "TENANT_B_ONLY"), ("other", "TENANT_A_ONLY")]:
        row = api.request(
            "POST", "/chat", {"message": "退货政策是什么"}, subject=subject, expected=200
        )
        assert excluded not in row.text and row.json()["citations"]
        stream = api.request(
            "POST",
            "/chat/stream",
            {"message": "退货政策是什么"},
            subject=subject,
            worker=1,
            expected=200,
        )
        events = [json.loads(x[5:]) for x in stream.text.splitlines() if x.startswith("data:")]
        answer = next(e["data"] for e in events if e["event"] == "answer")
        assert answer["citations"] and excluded not in stream.text and events[-1]["event"] == "done"


def test_parallel_queries_do_not_mix_request_scopes(api):
    def one(index):
        subject = "user" if index % 2 == 0 else "other"
        excluded = "TENANT_B_ONLY" if subject == "user" else "TENANT_A_ONLY"
        # Independent HTTP clients, no shared runner sequence mutation.
        import httpx

        from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import TOKENS

        with httpx.Client(timeout=15, trust_env=False) as client:
            r = client.post(
                api.processes[index % 2]["url"] + "/api/v1/knowledge/search",
                json={"query": "退货政策"},
                headers={"authorization": "Bearer " + TOKENS[subject]},
            )
            assert r.status_code == 200 and excluded not in r.text and r.json()["chunks"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one, range(12)))


def test_foreign_cache_payload_is_never_returned(api):
    from redis.asyncio import Redis

    async def poison():
        client = Redis.from_url(api.cfg["redis_url"], decode_responses=True)
        try:
            keys = [k async for k in client.scan_iter(match="private-ret:v1:*")]
            assert len(keys) >= 2
            for key in keys:
                await client.set(key, json.dumps(["FOREIGN_CHUNK_SENTINEL"]), ex=60)
        finally:
            await client.aclose()

    asyncio.run(poison())
    for subject, excluded in [("user", "TENANT_B_ONLY"), ("other", "TENANT_A_ONLY")]:
        assert excluded not in json.dumps(query(api, subject))


def test_concurrent_updates_remain_atomic_across_workers(api):
    identifier = "concurrent_owned"
    put(api, identifier, "退货政策 原始版本")
    import httpx

    from research.docs.agent_engineering_upgrade.p4_dependency_integration.worker import TOKENS

    def write(index):
        with httpx.Client(timeout=15, trust_env=False) as client:
            r = client.put(
                api.processes[index % 2]["url"] + "/api/v1/knowledge/documents/" + identifier,
                json={"title": "parallel", "content": "退货政策 ATOMIC_REV_" + str(index)},
                headers={"authorization": "Bearer " + TOKENS["user"]},
            )
            assert r.status_code == 200

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(write, range(2)))
    result = query(api, worker=1)
    own = [c for c in result["chunks"] if c["document_id"] == identifier]
    assert own and len({c["policy_version"] for c in own}) == 1
    assert all("ATOMIC_REV_" in c["content"] for c in own)


def test_private_endpoints_explicitly_disabled_in_public_mode():
    run = Runtime(mode="public", count=1)
    try:
        run.start()
        run.request("POST", "/knowledge/search", {"query": "policy"}, expected=403)
        run.request(
            "POST",
            "/knowledge/documents/denied",
            {"title": "policy", "content": "sentinel"},
            expected=403,
        )
    finally:
        run.stop()


def test_old_revision_cleanup_cannot_delete_new_revision(api):
    from app.retrieval.private import PrivateVectorStore
    from app.schemas.retrieval import RetrievedChunk

    store = PrivateVectorStore(api.cfg["qdrant_url"], api.cfg["collection"] + "_revision_probe", 2)
    try:
        store.ensure_collection()
        chunks = [
            RetrievedChunk(
                chunk_id=api.directory.name + revision,
                document_id="same",
                title="synthetic",
                content="synthetic",
                score=0,
                policy_version=revision,
                metadata={"tenant_subject": api.subjects["user"], "revision": revision},
            )
            for revision in ["old", "new"]
        ]
        store.write(chunks, [[1.0, 0.0], [0.0, 1.0]])
        store.remove_document(api.subjects["user"], "same", revision="old")
        hits = store.scoped_search(
            api.subjects["user"], [c.chunk_id for c in chunks], [0.0, 1.0], 5
        )
        assert [h[0] for h in hits] == [chunks[1].chunk_id]
    finally:
        if store._client is not None:
            store._client.close()


def test_fresh_process_reloads_same_authorized_sql_corpus(api):
    fresh = Runtime(count=1)
    fresh.subjects = dict(api.subjects)
    try:
        fresh.start()
        result = query(fresh)
        assert "TENANT_A_ONLY" in json.dumps(result)
        assert "TENANT_B_ONLY" not in json.dumps(result)
    finally:
        fresh.stop()
