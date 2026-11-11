"""Adversarial real adapter probe; report missing private-KB isolation as FAIL."""

import inspect
import json
from pathlib import Path

from app.main import create_app  # noqa: F401 -- initialize application import graph
from app.retrieval.vector import QdrantVectorStore, VectorRecord
from app.schemas.retrieval import RetrievedChunk
from research.docs.agent_engineering_upgrade.p4_dependency_integration.sandbox import (
    command,
    live_config,
)


def main():
    manifest, cfg = live_config()
    command(manifest, "ps")
    store = QdrantVectorStore(cfg["qdrant_url"], cfg["collection"] + "_tenant_adversarial", 2)
    try:
        store.upsert(
            [
                VectorRecord(
                    RetrievedChunk(
                        chunk_id="p4e_tenant_a_sentinel",
                        document_id="p4e_tenant_a",
                        title="synthetic private sentinel",
                        content="P4E_SYNTHETIC_TENANT_A_ONLY",
                        score=1,
                        metadata={"tenant_id": "tenant_a"},
                    ),
                    [1.0, 0.0],
                )
            ]
        )
        hits = store.search([1.0, 0.0], top_k=1)
        assert hits and hits[0].content == "P4E_SYNTHETIC_TENANT_A_ONLY"
        payload = store._client.scroll(store._collection, limit=1, with_payload=True)[0][0].payload
        result = {
            "private_multi_tenant_KB_acceptance": "FAIL",
            "probe": "REAL_QDRANT_APPLICATION_ADAPTER_SYNTHETIC_SENTINEL",
            "search_parameters": list(inspect.signature(store.search).parameters),
            "tenant_metadata_preserved": "tenant_id" in payload,
            "sentinel_returned_without_owner": True,
            "native_Qdrant_filter_test_is_not_app_filter": True,
            "cross_user_HTTP_private_KB": "NOT_ASSESSED_NO_TENANT_INGEST_OR_QUERY_CONTRACT",
            "root_cause": "shared public corpus adapter has neither tenant payload nor request-scoped filter; BM25/cache also shared",
            "disposition": "BLOCK private multi-tenant deployment; public non-sensitive KB only. End-to-end ACL requires coordinated ingest/BM25/vector/cache changes, not an isolated vector-only patch",
            "no_real_private_data_used": True,
        }
        path = Path(__file__).parent / "evidence/e1_tenant_RED.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print("Tenant private-KB acceptance FAIL retained; synthetic adapter probe completed")
    finally:
        if store._client is not None:
            store._client.close()


if __name__ == "__main__":
    main()
