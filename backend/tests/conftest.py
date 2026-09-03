import pytest
from fastapi.testclient import TestClient

from backend.app.api import routes
from backend.app.main import app


@pytest.fixture(autouse=True)
def clear_in_memory_store() -> None:
    routes.sourcing_requests.clear()
    routes.quotes_by_request.clear()
    routes.workflow_states.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
