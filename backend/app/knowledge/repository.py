import math
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import KnowledgeChunk
from .embeddings import validate_embedding

SOURCE_TYPES = {
    "part_reference_note", "vehicle_compatibility", "substitution_rule",
    "procurement_policy", "call_policy",
}


class KnowledgeRepository:
    """PostgreSQL exact cosine search over a small, curated corpus."""
    def __init__(self, session: Session, model_id: str):
        if session.get_bind().dialect.name != "postgresql":
            raise ValueError("Runtime vector retrieval requires PostgreSQL + pgvector")
        self.session = session
        self.model_id = model_id

    def add_chunk(self, *, source_type: str, source_ref: str, title: str,
                  content: str, embedding: list[float], metadata_json: dict) -> KnowledgeChunk:
        if source_type not in SOURCE_TYPES or metadata_json.get("curated") is not True:
            raise ValueError("Only curated reference/policy knowledge is accepted")
        if not content.strip() or len(content) > 2000:
            raise ValueError("Curated chunks must contain 1–2000 characters")
        validate_embedding(embedding)
        chunk = KnowledgeChunk(
            id=str(uuid4()), source_type=source_type, source_ref=source_ref,
            title=title, content=content, embedding=embedding,
            metadata_json={**metadata_json, "embedding_model": self.model_id},
        )
        self.session.add(chunk)
        self.session.flush()
        return chunk

    def _filtered(self, filters: dict | None):
        statement = select(KnowledgeChunk).where(
            KnowledgeChunk.source_type.in_(SOURCE_TYPES),
            KnowledgeChunk.metadata_json["curated"].as_boolean() == True,
            KnowledgeChunk.metadata_json["embedding_model"].as_string() == self.model_id,
        )
        for key, value in (filters or {}).items():
            if key not in {"source_type", "source_ref"}:
                raise ValueError("Unsupported knowledge filter")
            statement = statement.where(getattr(KnowledgeChunk, key) == value)
        return statement

    def search_similar(self, query_embedding: list[float], limit: int = 4,
                       filters: dict | None = None) -> list[KnowledgeChunk]:
        validate_embedding(query_embedding)
        if not 1 <= limit <= 5:
            raise ValueError("Knowledge retrieval limit must be between 1 and 5")
        distance = KnowledgeChunk.embedding.cosine_distance(query_embedding)
        statement = self._filtered(filters).order_by(distance, KnowledgeChunk.id).limit(limit)
        return list(self.session.scalars(statement))


class FakeKnowledgeRepository(KnowledgeRepository):
    """Explicit SQLite test/demo adapter; cosine is computed in Python."""
    def __init__(self, session: Session, model_id: str):
        if session.get_bind().dialect.name != "sqlite":
            raise ValueError("Fake retrieval is isolated to SQLite")
        self.session = session
        self.model_id = model_id

    def search_similar(self, query_embedding: list[float], limit: int = 4,
                       filters: dict | None = None) -> list[KnowledgeChunk]:
        validate_embedding(query_embedding)
        if not 1 <= limit <= 5:
            raise ValueError("Knowledge retrieval limit must be between 1 and 5")
        chunks = list(self.session.scalars(self._filtered(filters)))

        def distance(chunk):
            vector = chunk.embedding
            validate_embedding(vector)
            dot = sum(a * b for a, b in zip(query_embedding, vector))
            norms = math.sqrt(sum(x*x for x in vector) * sum(x*x for x in query_embedding))
            return (1 - dot / norms, chunk.id)

        return sorted(chunks, key=distance)[:limit]
