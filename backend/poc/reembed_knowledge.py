"""Idempotently replace curated knowledge embeddings with the configured model."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.models import KnowledgeChunk
from backend.app.db.session import get_session_factory
from backend.app.knowledge.embeddings import EmbeddingProvider, create_embedding_provider


def reembed_curated_knowledge(session: Session, embeddings: EmbeddingProvider) -> int:
    chunks = list(session.scalars(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.metadata_json["curated"].as_boolean() == True)
        .order_by(KnowledgeChunk.id)
    ))
    pending = [
        chunk for chunk in chunks
        if chunk.metadata_json.get("embedding_model") != embeddings.model_id
    ]
    if not pending:
        return 0
    vectors = embeddings.embed_documents([chunk.content for chunk in pending])
    for chunk, vector in zip(pending, vectors, strict=True):
        chunk.embedding = vector
        chunk.metadata_json = {**chunk.metadata_json, "embedding_model": embeddings.model_id}
    session.flush()
    return len(pending)


def main() -> None:
    if settings.rag_mode != "postgres":
        raise SystemExit("Re-embedding requires RAG_MODE=postgres")
    embeddings = create_embedding_provider(
        settings.rag_embedding_provider, settings.rag_embedding_model
    )
    with get_session_factory()() as session:
        updated = reembed_curated_knowledge(session, embeddings)
        session.commit()
    print(f"Curated knowledge rows re-embedded: {updated}")


if __name__ == "__main__":
    main()
