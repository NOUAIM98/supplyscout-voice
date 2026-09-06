import json
import socket

import pytest
from calle.calls import CalleCalls
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from backend.app.agent.graph import ProcurementAgent
from backend.app.agent.nodes import AgentDependencies
from backend.app.api import routes
from backend.app.config import settings, Settings
from backend.app.db.models import KnowledgeChunk, SourcingRequest, SupplierQuote
from backend.app.knowledge.demo import seed_demo
from backend.app.knowledge.embeddings import FakeEmbeddingProvider
from backend.app.knowledge.repository import FakeKnowledgeRepository, KnowledgeRepository
from backend.app.knowledge.service import (
    ProcurementKnowledgeRetriever, build_retriever, compose_quote_context, provenance,
)
from backend.tests.test_phase_a import create_request, approve_quotes


@pytest.fixture(autouse=True)
def offline_rag(monkeypatch):
    monkeypatch.setattr(settings, "rag_mode", "fake")
    monkeypatch.setattr(settings, "app_env", "test")

    def forbidden(*args, **kwargs):
        raise AssertionError("No network or CALL-E operation allowed")

    original_connect = socket.socket.connect

    def external_connections_blocked(sock, address):
        # Windows asyncio uses a loopback socketpair for its internal wakeup pipe.
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        forbidden()

    monkeypatch.setattr(socket.socket, "connect", external_connections_blocked)
    monkeypatch.setattr(CalleCalls, "create", forbidden)


@pytest.fixture
def knowledge(session_factory):
    with session_factory() as session:
        embeddings = FakeEmbeddingProvider()
        repository = FakeKnowledgeRepository(session, embeddings.model_id)
        assert seed_demo(repository, embeddings) == 5
        assert seed_demo(repository, embeddings) == 0
        session.commit()


def test_embeddings_deterministic():
    provider = FakeEmbeddingProvider()
    a = provider.embed_query("Renault Clio alternator")
    assert a == FakeEmbeddingProvider().embed_documents(["Renault Clio alternator"])[0]
    assert len(a) == 384
    assert a != provider.embed_query("substitution policy")


def test_chunks_persist_with_model_identity(knowledge, session_factory):
    with session_factory() as session:
        chunks = list(session.scalars(select(KnowledgeChunk)))
        assert len(chunks) == 5
        assert all(c.metadata_json["embedding_model"] == FakeEmbeddingProvider.model_id for c in chunks)
        assert all(c.created_at and c.updated_at for c in chunks)


def test_reference_substitution_provenance_and_limit(knowledge, client):
    request_id = create_request(client)
    response = client.post(f"/api/v1/sourcing-requests/{request_id}/context-preview")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "fake" and data["call_started"] is False
    assert len(data["chunks"]) == 4
    types = {c["source_type"] for c in data["chunks"]}
    assert {"part_reference_note", "substitution_rule"} <= types
    assert all(set(c) == {"id", "title", "source_type", "source_ref", "snippet"} for c in data["chunks"])
    assert "embedding" not in json.dumps(data)
    assert "supplier has stock" not in data["task_context"]
    assert "145" not in data["task_context"]
    assert "Unknown stays unknown" in data["task_context"]
    assert client.get(f"/api/v1/sourcing-requests/{request_id}/quotes").json() == []
    assert client.get(f"/api/v1/sourcing-requests/{request_id}/workflow").json()["workflow_status"] == "request_created"


@pytest.mark.parametrize("limit", [1, 3, 5])
def test_configured_top_k(knowledge, session_factory, client, limit):
    request_id = create_request(client)
    with session_factory() as session:
        provider = FakeEmbeddingProvider()
        retriever = ProcurementKnowledgeRetriever(FakeKnowledgeRepository(session, provider.model_id), provider, limit)
        assert len(retriever.retrieve(session.get(SourcingRequest, request_id))) == limit


def test_filters_and_model_isolation(knowledge, session_factory):
    with session_factory() as session:
        provider = FakeEmbeddingProvider()
        repository = FakeKnowledgeRepository(session, provider.model_id)
        query = provider.embed_query("reference")
        assert len(repository.search_similar(query, filters={"source_type": "substitution_rule"})) == 1
        assert FakeKnowledgeRepository(session, "other-model").search_similar(query) == []
        with pytest.raises(ValueError):
            repository.search_similar(query, filters={"supplier_price": "145"})


def test_context_before_preview_and_ids_persist(knowledge, client, session_factory):
    request_id = create_request(client)
    with session_factory() as session:
        agent = ProcurementAgent(AgentDependencies(session, routes.provider))
        state, transitions = agent.run_with_transitions(agent.initial_state(request_id))
        assert transitions == ["context_retrieval", "call_preview", "awaiting_quote_approval"]
        assert state["quote_call_approved"] is False
        assert len(state["knowledge_chunk_ids"]) == 4
        session.commit()
    with session_factory() as session:
        assert session.get(SourcingRequest, request_id).knowledge_chunk_ids == state["knowledge_chunk_ids"]


def test_rag_ranking_and_unknown_facts_unchanged(knowledge, client, monkeypatch):
    def flow(mode):
        monkeypatch.setattr(settings, "rag_mode", mode)
        request_id = create_request(client)
        quotes = approve_quotes(client, request_id)
        ranking = client.get(f"/api/v1/sourcing-requests/{request_id}/ranking").json()
        return [{k: v for k, v in q.items() if k not in {"id", "sourcing_request_id", "created_at"}} for q in quotes], [r["supplier_name"] for r in ranking["ranking"]]
    assert flow("fake") == flow("disabled")


def test_preview_does_not_call_even_fake_provider(knowledge, client, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Preview cannot invoke calls")
    monkeypatch.setattr(routes.provider, "create_quote_call", forbidden)
    monkeypatch.setattr(routes.provider, "create_reservation_call", forbidden)
    request_id = create_request(client)
    for endpoint in ["context-preview", "quote-preview"]:
        assert client.post(f"/api/v1/sourcing-requests/{request_id}/{endpoint}").status_code == 200
    assert client.post(f"/api/v1/sourcing-requests/{request_id}/approve-reservation").status_code == 409


def test_context_reaches_call_task_without_executing(knowledge, client, session_factory):
    from backend.app.providers.calls.calle import CalleCallProvider
    request_id = create_request(client)
    with session_factory() as session:
        request = session.get(SourcingRequest, request_id)
        retriever = build_retriever(session)
        context = compose_quote_context(retriever.retrieve(request))
        supplier = routes.provider.suppliers()[0]
        provider = CalleCallProvider(api_key="test-only", recipients={supplier.id: {
            "phones": [supplier.phone_e164], "region": "FR", "locale": "fr-FR",
        }})
        payload = provider.build_quote_request(request, supplier, knowledge_context=context)
        assert context in payload["task"]
        assert "demo:clio:substitution:v1" in payload["task"]
        assert payload["idempotency_key"] == provider.quote_idempotency_key(request.id, supplier.id)


def test_postgres_boundary_and_ddl(session_factory, monkeypatch):
    with session_factory() as session:
        with pytest.raises(ValueError, match="PostgreSQL"):
            KnowledgeRepository(session, "real-model")
        monkeypatch.setattr(settings, "rag_mode", "postgres")
        with pytest.raises(ValueError, match="real embedding provider"):
            build_retriever(session)
    ddl = str(CreateTable(KnowledgeChunk.__table__).compile(dialect=postgresql.dialect()))
    assert "VECTOR(384)" in ddl
    query = select(KnowledgeChunk.id).order_by(KnowledgeChunk.embedding.cosine_distance([1.0] * 384)).limit(4)
    assert "<=>" in str(query.compile(dialect=postgresql.dialect()))


def test_fake_disabled_in_production(session_factory, monkeypatch, client):
    monkeypatch.setattr(settings, "app_env", "production")
    with session_factory() as session:
        with pytest.raises(ValueError, match="development/test"):
            build_retriever(session)
    request_id = create_request(client)
    assert client.post(f"/api/v1/sourcing-requests/{request_id}/context-preview").status_code == 404


def test_fake_without_api_key(monkeypatch):
    monkeypatch.delenv("CALLE_API_KEY", raising=False)
    config = Settings(_env_file=None)
    assert config.call_provider_mode == "fake"
    assert config.calle_api_key is None


def test_reject_live_source_and_bad_embedding(session_factory):
    with session_factory() as session:
        repository = FakeKnowledgeRepository(session, FakeEmbeddingProvider.model_id)
        with pytest.raises(ValueError, match="curated"):
            repository.add_chunk(source_type="supplier_quote", source_ref="bad", title="bad",
                content="live stock", embedding=[1.0] * 384, metadata_json={"curated": True})
        with pytest.raises(ValueError, match="384"):
            repository.search_similar([1.0])


def test_postgres_migration_offline(monkeypatch):
    from io import StringIO
    from alembic import command
    from alembic.config import Config
    output = StringIO()
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://localhost/compile_only")
    config = Config("alembic.ini", output_buffer=output)
    command.upgrade(config, "549733be0747:head", sql=True)
    sql = output.getvalue()
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "VECTOR(384)" in sql
    assert "knowledge_chunk_ids" in sql


def test_alembic_accepts_percent_encoded_database_password(monkeypatch):
    from io import StringIO
    from alembic import command
    from alembic.config import Config
    output = StringIO()
    fictional_url = "postgresql+psycopg://demo:p%40ss%25word%2Fvalue@localhost/demo"
    monkeypatch.setattr(settings, "database_url", fictional_url)
    config = Config("alembic.ini", output_buffer=output)
    command.upgrade(config, "549733be0747:head", sql=True)
    assert "CREATE TABLE knowledge_chunks" in output.getvalue()


def test_sqlite_migration_round_trip(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect
    url = "sqlite:///" + str(tmp_path / "migration_test.db")
    monkeypatch.setattr(settings, "database_url", url)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(url)
    try:
        assert "knowledge_chunks" in inspect(engine).get_table_names()
        command.downgrade(config, "549733be0747")
        assert "knowledge_chunks" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        assert "knowledge_chunks" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_approved_fake_dispatch_receives_preview_context(knowledge, client, monkeypatch):
    captured = []
    original = routes.provider.create_quote_call

    def capture(*args, **kwargs):
        captured.append(kwargs["knowledge_context"])
        return original(*args, **kwargs)

    monkeypatch.setattr(routes.provider, "create_quote_call", capture)
    request_id = create_request(client)
    client.post(f"/api/v1/sourcing-requests/{request_id}/quote-preview")
    assert captured == []
    approve_quotes(client, request_id)
    assert len(captured) == 3
    assert all("demo:clio:substitution:v1" in text for text in captured)
