import pytest
from pydantic import ValidationError

from app.config.settings import Settings
from app.main import create_app  # noqa: F401 -- bootstrap existing import graph


def test_private_knowledge_requires_verified_authentication():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None, app_env="testing", auth_mode="legacy_test", knowledge_mode="private"
        )


def test_private_mode_is_an_explicit_setting():
    assert Settings(_env_file=None, knowledge_mode="private").knowledge_mode == "private"


@pytest.mark.asyncio
async def test_private_retriever_never_uses_unscoped_access():
    from app.core.exceptions import ToolPermissionError
    from app.retrieval.private import PrivateKnowledgeRetriever

    retriever = PrivateKnowledgeRetriever(None, None, None, rrf_k=60, ttl=10)
    with pytest.raises(ToolPermissionError):
        await retriever.retrieve("private", top_k=3)


@pytest.mark.parametrize("field", ["title", "content"])
def test_private_document_rejects_blank_text(field):
    from app.api.routes.knowledge import DocumentInput

    payload = {"title": "合成政策", "content": "有效合成政策"}
    payload[field] = " \n\t "
    with pytest.raises(ValidationError):
        DocumentInput.model_validate(payload)


def test_tokenless_bm25_corpus_is_safe_empty_result():
    from app.retrieval.bm25 import BM25Retriever
    from app.schemas.retrieval import RetrievedChunk

    retriever = BM25Retriever(
        [
            RetrievedChunk(
                chunk_id="empty", document_id="empty", title="empty", content=" \n ", score=0
            )
        ]
    )
    assert retriever.search("policy", top_k=3) == []
