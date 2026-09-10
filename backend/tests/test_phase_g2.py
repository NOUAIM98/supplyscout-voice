import pytest

from backend.app.config import Settings
from backend.app.knowledge import warmup


def test_cors_defaults_to_localhost() -> None:
    configured = Settings(_env_file=None)
    assert configured.allowed_cors_origins == ("http://localhost:3000",)


def test_cors_accepts_production_https_origin() -> None:
    configured = Settings(
        _env_file=None, cors_allowed_origins="https://supplyscout.example.com"
    )
    assert configured.allowed_cors_origins == ("https://supplyscout.example.com",)


def test_cors_parses_multiple_origins_and_ignores_whitespace() -> None:
    configured = Settings(
        _env_file=None,
        cors_allowed_origins=" http://localhost:3000, ,https://supplyscout.example.com ",
    )
    assert configured.allowed_cors_origins == (
        "http://localhost:3000",
        "https://supplyscout.example.com",
    )


def test_cors_rejects_wildcard() -> None:
    configured = Settings(_env_file=None, cors_allowed_origins="*")
    with pytest.raises(ValueError, match="wildcard"):
        configured.allowed_cors_origins


def test_health_returns_only_safe_status(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_embedding_warmup_validates_configured_model(monkeypatch) -> None:
    calls = []

    class Provider:
        def embed_query(self, text):
            calls.append(text)

    monkeypatch.setattr(warmup.settings, "rag_mode", "postgres")
    monkeypatch.setattr(warmup, "create_embedding_provider", lambda *_: Provider())
    warmup.main()
    assert calls == ["SupplyScout semantic model startup check"]
