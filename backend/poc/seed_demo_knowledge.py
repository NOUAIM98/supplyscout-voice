"""Explicit SQLite fake-RAG seed; never contacts CALL-E or an embedding service."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.config import settings
from backend.app.db.session import get_session_factory
from backend.app.knowledge.demo import seed_demo
from backend.app.knowledge.service import build_retriever


def main():
    if settings.rag_mode != "fake" or settings.app_env not in {"development", "test"}:
        raise SystemExit("Demo seeding requires RAG_MODE=fake and development/test")
    with get_session_factory().begin() as session:
        retriever = build_retriever(session)
        added = seed_demo(retriever.repository, retriever.embeddings)
    print(f"Fake demo knowledge chunks added: {added}")


if __name__ == "__main__":
    main()
