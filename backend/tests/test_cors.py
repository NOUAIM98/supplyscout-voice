import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from backend.app.config import Settings


def test_cors_defaults_to_localhost() -> None:
    configured = Settings(_env_file=None)
    assert configured.allowed_cors_origins == ("http://localhost:3000",)


def test_cors_parses_multiple_origins_and_strips_whitespace() -> None:
    configured = Settings(
        _env_file=None,
        cors_allowed_origins=(
            " http://localhost:3000, ,https://supplyscout-voice.vercel.app "
        ),
    )
    assert configured.allowed_cors_origins == (
        "http://localhost:3000",
        "https://supplyscout-voice.vercel.app",
    )


def test_cors_empty_values_fall_back_to_localhost() -> None:
    configured = Settings(_env_file=None, cors_allowed_origins=" ,  ,")
    assert configured.allowed_cors_origins == ("http://localhost:3000",)


def test_cors_rejects_wildcard() -> None:
    configured = Settings(
        _env_file=None,
        cors_allowed_origins="http://localhost:3000,*",
    )
    with pytest.raises(ValueError, match="wildcard"):
        configured.allowed_cors_origins


def test_cors_middleware_accepts_production_vercel_origin() -> None:
    configured = Settings(
        _env_file=None,
        cors_allowed_origins=(
            "http://localhost:3000,https://supplyscout-voice.vercel.app"
        ),
    )
    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=list(configured.allowed_cors_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @test_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    response = TestClient(test_app).get(
        "/health",
        headers={"Origin": "https://supplyscout-voice.vercel.app"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "https://supplyscout-voice.vercel.app"
    )
