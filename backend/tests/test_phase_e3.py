import json

import pytest
from sqlalchemy import select

from backend.app.api import routes
from backend.app.config import Settings, settings
from backend.app.db.models import KnowledgeChunk
from backend.app.knowledge.embeddings import (
    FastEmbedEmbeddingProvider, FakeEmbeddingProvider, create_embedding_provider,
)
from backend.app.knowledge.service import build_retriever
from backend.poc.reembed_knowledge import reembed_curated_knowledge
from backend.tests.test_phase_a import create_request


class Array:
    def __init__(self, values):
        self.values = values

    def tolist(self):
        return self.values


class Model:
    def embed(self, texts):
        return (Array([float(index + 1)] * 384) for index, _ in enumerate(texts))


def test_fastembed_provider_returns_valid_384_dimensions() -> None:
    provider = FastEmbedEmbeddingProvider(model=Model())
    assert provider.model_id == "BAAI/bge-small-en-v1.5"
    assert provider.dimensions == 384
    assert len(provider.embed_query("semantic query")) == 384
    assert all(len(vector) == 384 for vector in provider.embed_documents(["one", "two"]))


def test_configured_provider_factory(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(
        "backend.app.knowledge.embeddings.FastEmbedEmbeddingProvider",
        lambda model_id, cache_dir=None: (model_id, cache_dir, sentinel),
    )
    assert create_embedding_provider("fastembed", "model", "/tmp/cache") == (
        "model", "/tmp/cache", sentinel,
    )
    with pytest.raises(ValueError, match="FastEmbed"):
        create_embedding_provider("unknown", "model")


def test_postgres_mode_constructs_real_provider(monkeypatch, session_factory) -> None:
    provider = FastEmbedEmbeddingProvider(model=Model())
    captured = {}

    class Repository:
        def __init__(self, session, model_id):
            captured["model_id"] = model_id
            self.model_id = model_id

    monkeypatch.setattr(settings, "rag_mode", "postgres")
    monkeypatch.setattr("backend.app.knowledge.service.create_embedding_provider", lambda *_: provider)
    monkeypatch.setattr("backend.app.knowledge.service.KnowledgeRepository", Repository)
    with session_factory() as session:
        retriever = build_retriever(session)
    assert retriever.embeddings is provider
    assert captured["model_id"] == provider.model_id


def test_postgres_mode_rejects_fake_provider(monkeypatch, session_factory) -> None:
    monkeypatch.setattr(settings, "rag_mode", "postgres")
    with session_factory() as session, pytest.raises(ValueError, match="cannot use fake"):
        build_retriever(session, FakeEmbeddingProvider())


def test_production_context_preview_is_safe(monkeypatch, client) -> None:
    request_id = create_request(client)
    chunk = KnowledgeChunk(
        id="safe-chunk", source_type="procurement_policy", source_ref="safe:policy",
        title="Safe policy", content="Safe curated context", embedding=[1.0] * 384,
        metadata_json={"curated": True, "embedding_model": "semantic-model"},
    )

    class Retriever:
        def retrieve(self, request):
            return [chunk]

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "rag_mode", "postgres")
    monkeypatch.setattr(routes, "build_retriever", lambda session: Retriever())
    monkeypatch.setattr(routes.provider, "create_quote_call", lambda *args, **kwargs: pytest.fail("call started"))
    response = client.post(f"/api/v1/sourcing-requests/{request_id}/context-preview")
    assert response.status_code == 200
    data = response.json()
    assert data["call_started"] is False and len(data["chunks"]) == 1
    assert "embedding" not in json.dumps(data).lower()


def test_reembedding_is_idempotent_and_preserves_curated_rows(session_factory) -> None:
    with session_factory() as session:
        chunk = KnowledgeChunk(
            id="curated", source_type="procurement_policy", source_ref="safe:policy",
            title="Policy", content="Curated content", embedding=[1.0] * 384,
            metadata_json={"curated": True, "embedding_model": "old-model"},
        )
        session.add(chunk)
        session.commit()
        provider = FastEmbedEmbeddingProvider(model=Model())
        assert reembed_curated_knowledge(session, provider) == 1
        assert reembed_curated_knowledge(session, provider) == 0
        stored = session.scalar(select(KnowledgeChunk).where(KnowledgeChunk.id == "curated"))
        assert stored.source_ref == "safe:policy"
        assert stored.metadata_json["embedding_model"] == provider.model_id
        assert len(stored.embedding) == 384


def test_rag_settings_are_safe_by_default() -> None:
    configured = Settings(_env_file=None)
    assert configured.rag_mode == "disabled"
    assert configured.rag_embedding_provider == "fastembed"
    assert configured.rag_embedding_model == "BAAI/bge-small-en-v1.5"
