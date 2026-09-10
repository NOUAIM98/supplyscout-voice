"""Download and validate the configured production embedding model before startup."""

from ..config import settings
from .embeddings import create_embedding_provider


def main() -> None:
    if settings.rag_mode != "postgres":
        return
    provider = create_embedding_provider(
        settings.rag_embedding_provider,
        settings.rag_embedding_model,
        settings.rag_embedding_cache_dir,
    )
    provider.embed_query("SupplyScout semantic model startup check")
    print("Semantic embedding model ready")


if __name__ == "__main__":
    main()
