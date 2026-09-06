import hashlib
import math
import re
from typing import Protocol

DIMENSIONS = 384


class EmbeddingProvider(Protocol):
    model_id: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def validate_embedding(vector: list[float]) -> None:
    if len(vector) != DIMENSIONS or not all(math.isfinite(x) for x in vector):
        raise ValueError("Embedding must contain 384 finite values")
    if not any(vector):
        raise ValueError("Cosine retrieval requires a nonzero embedding")


class FakeEmbeddingProvider:
    """Offline hashed token counts for tests/demo, NOT semantic embeddings."""
    model_id = "fake-sha256-token-v1"
    dimensions = DIMENSIONS

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * DIMENSIONS
        for token in re.findall(r"[\w-]+", text.lower()):
            bucket = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4]) % DIMENSIONS
            vector[bucket] += 1
        length = math.sqrt(sum(x * x for x in vector))
        if not length:
            raise ValueError("Embedding text cannot be empty")
        return [x / length for x in vector]
