from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, NoReturn

import httpx
import pytest

from backend.app.config import Settings
from backend.app.db.models import SourcingRequest, Supplier
from backend.app.domain.ranking import rank_quotes
from backend.app.providers.calls.calle import (
    CALLE_QUOTE_SCHEMA,
    CalleCallProvider,
    CalleResultError,
)
from backend.app.providers.calls.factory import create_call_provider
from backend.app.providers.calls.fake import FakeCallProvider


class StubCalls:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.created: list[dict[str, Any]] = []
        self.gotten: list[str] = []

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.created.append(kwargs)
        return self.response

    def get(self, call_id: str) -> dict[str, Any]:
        self.gotten.append(call_id)
        return self.response

    def list_events(
        self, call_id: str, *, cursor: str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        return {"call_id": call_id, "cursor": cursor, "limit": limit, "events": []}


class StubClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.calls = StubCalls(response)


def sourcing_request(request_id: str = "request-001") -> SourcingRequest:
    now = datetime.now(timezone.utc)
    return SourcingRequest(
        id=request_id,
        vehicle_make="Renault",
        vehicle_model="Clio",
        vehicle_year=2019,
        part_name="Alternator",
        requested_reference="TEST-ALT-CLIO-2019-001",
        quantity=1,
        max_budget=Decimal("180.00"),
        currency="EUR",
        needed_by=date.today(),
        status="draft",
        created_at=now,
        updated_at=now,
    )


def supplier(supplier_id: str = "supplier-001") -> Supplier:
    now = datetime.now(timezone.utc)
    return Supplier(
        id=supplier_id,
        name="Authorized Test Supplier",
        phone_e164="+12025550104",
        authorized_for_calls=True,
        created_at=now,
        updated_at=now,
    )


def structured_response(
    *, confidence: float = 0.7, structured_result: Any = ...
) -> dict[str, Any]:
    if structured_result is ...:
        structured_result = {
            "exact_reference_confirmed": "yes",
            "offered_reference": "TEST-ALT-CLIO-2019-001",
            "in_stock": "yes",
            "condition": "new",
            "unit_price": 145,
            "currency": "EUR",
            "tax_included": "unknown",
            "warranty_months": 12,
            "pickup_available_today": "yes",
        }
    return {
        "id": "call-test-001",
        "status": "completed",
        "recipients": [
            {
                "structured_result": structured_result,
                "task_completed": True,
                "completion_confidence": confidence,
                "evidence": ["supplier statement"],
                "failure_code": None,
                "failure_message": None,
            }
        ],
    }


def calle_provider(
    response: dict[str, Any] | None = None,
    *,
    recipient: dict[str, Any] | None = None,
) -> tuple[CalleCallProvider, StubClient]:
    test_supplier = supplier()
    client = StubClient(response or structured_response())
    provider = CalleCallProvider(
        api_key="test-placeholder-key",
        recipients={
            test_supplier.id: recipient
            or {"phones": [test_supplier.phone_e164], "region": "US", "locale": "en-US"}
        },
        client=client,
    )
    return provider, client


def test_fake_is_default_and_requires_no_api_key(monkeypatch) -> None:
    monkeypatch.delenv("CALL_PROVIDER_MODE", raising=False)
    monkeypatch.delenv("CALLE_API_KEY", raising=False)
    settings = Settings(_env_file=None)

    assert settings.call_provider_mode == "fake"
    assert isinstance(create_call_provider(settings), FakeCallProvider)


def test_calle_mode_requires_api_key_and_factory_selects_provider() -> None:
    with pytest.raises(RuntimeError, match="CALLE_API_KEY"):
        create_call_provider(
            Settings(_env_file=None, call_provider_mode="calle", calle_api_key=None)
        )

    provider = create_call_provider(
        Settings(
            _env_file=None,
            call_provider_mode="calle",
            calle_api_key="test-placeholder-key",
        ),
        client=StubClient(structured_response()),
    )
    assert isinstance(provider, CalleCallProvider)


def test_quote_schema_is_calle_compatible() -> None:
    forbidden = {"$ref", "oneOf", "anyOf", "allOf"}

    def keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value).union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert not forbidden.intersection(keys(CALLE_QUOTE_SCHEMA))
    assert CALLE_QUOTE_SCHEMA["additionalProperties"] is False
    assert CALLE_QUOTE_SCHEMA["properties"]["offered_reference"] == {
        "type": "string"
    }
    assert "offered_reference" not in CALLE_QUOTE_SCHEMA["required"]


def test_create_maps_recipient_schema_metadata_and_stable_idempotency() -> None:
    provider, client = calle_provider()
    request = sourcing_request()
    test_supplier = supplier()

    quote = provider.create_quote_call(request, test_supplier)
    payload = client.calls.created[0]

    assert quote.supplier_id == test_supplier.id
    assert payload["recipient"] == {
        "phones": ["+12025550104"],
        "region": "US",
        "locale": "en-US",
    }
    assert payload["recipient_result_schema"] is CALLE_QUOTE_SCHEMA
    assert payload["metadata"] == {
        "workflow_type": "supplier_quote",
        "sourcing_request_id": request.id,
        "supplier_id": test_supplier.id,
    }
    assert payload["idempotency_key"] == "supplyscout:quote:request-001:supplier-001"
    assert provider.quote_idempotency_key(request.id, test_supplier.id) == payload[
        "idempotency_key"
    ]
    assert "do not order, purchase, pay, reserve, or commit" in payload["task"]


def test_invalid_e164_is_rejected_before_sdk_invocation() -> None:
    provider, client = calle_provider(
        recipient={"phones": ["not-a-phone"], "region": "US", "locale": "en-US"}
    )

    with pytest.raises(ValueError, match="E.164"):
        provider.create_quote_call(sourcing_request(), supplier())

    assert client.calls.created == []


def test_structured_result_normalizes_and_retains_safe_provider_data() -> None:
    provider, _ = calle_provider()
    quote = provider.create_quote_call(sourcing_request(), supplier())

    assert quote.exact_reference_confirmed == "yes"
    assert quote.unit_price == Decimal("145")
    assert quote.manufacturer_or_brand is None
    assert provider.provider_results[supplier().id] == {
        "call_id": "call-test-001",
        "status": "completed",
        "task_completed": True,
        "completion_confidence": 0.7,
        "evidence": ["supplier statement"],
        "failure_code": None,
        "failure_message": None,
    }


def test_null_structured_result_preserves_failure_without_guessed_quote() -> None:
    provider, _ = calle_provider(structured_response(structured_result=None))

    with pytest.raises(CalleResultError, match="no structured"):
        provider.create_quote_call(sourcing_request(), supplier())

    assert provider.provider_results[supplier().id]["call_id"] == "call-test-001"


def test_completion_confidence_does_not_change_deterministic_ranking() -> None:
    request = sourcing_request()
    first_supplier = supplier("supplier-001")
    second_supplier = supplier("supplier-002")
    second_supplier.name = "Second Test Supplier"
    low_provider, _ = calle_provider(structured_response(confidence=0.1))
    high_provider = CalleCallProvider(
        api_key="test-placeholder-key",
        recipients={
            second_supplier.id: {
                "phones": [second_supplier.phone_e164],
                "region": "US",
                "locale": "en-US",
            }
        },
        client=StubClient(structured_response(confidence=0.99)),
    )
    low_quote = low_provider.create_quote_call(request, first_supplier)
    high_quote = high_provider.create_quote_call(request, second_supplier)
    high_quote.unit_price = Decimal("150")

    ranked = rank_quotes(
        request,
        [high_quote, low_quote],
        {first_supplier.id: first_supplier, second_supplier.id: second_supplier},
    )

    assert ranked[0].quote.id == low_quote.id


def test_get_and_events_use_stub_only() -> None:
    provider, client = calle_provider()
    quote = provider.get_quote_result("call-test-001", sourcing_request(), supplier())
    events = provider.list_events("call-test-001", cursor="next", limit=10)

    assert quote.unit_price == Decimal("145")
    assert client.calls.gotten == ["call-test-001"]
    assert events == {
        "call_id": "call-test-001",
        "cursor": "next",
        "limit": 10,
        "events": [],
    }


def test_reservation_requires_separate_approval_before_sdk_invocation() -> None:
    provider, client = calle_provider()
    quote = provider.normalize_quote_response(
        structured_response(), sourcing_request(), supplier()
    )

    with pytest.raises(PermissionError, match="reservation approval"):
        provider.create_reservation_call(sourcing_request(), quote, supplier())

    assert client.calls.created == []


def test_stubbed_provider_makes_no_http_request(monkeypatch) -> None:
    def fail_if_requested(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError("An actual HTTP request was attempted")

    monkeypatch.setattr(httpx.Client, "request", fail_if_requested)
    provider, _ = calle_provider()

    provider.create_quote_call(sourcing_request(), supplier())
