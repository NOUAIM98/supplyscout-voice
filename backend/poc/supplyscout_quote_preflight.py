import inspect
import os
import ssl
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from calle.calls import CalleCalls
from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.db.models import SourcingRequest, Supplier
from backend.app.providers.calls.calle import (
    CALLE_QUOTE_SCHEMA,
    E164_PATTERN,
    CalleCallProvider,
)


REQUEST_ID = "demo-clio-alternator-001"
SUPPLIER_ID = "test-supplier-001"


def mask_phone(phone: str) -> str:
    if len(phone) < 7:
        return "******"
    return f"{phone[:3]}******{phone[-3:]}"


def load_configuration() -> dict[str, str]:
    backend_dir = Path(__file__).resolve().parents[1]
    load_dotenv(backend_dir / ".env", override=False)
    return {
        "api_key": (os.getenv("CALLE_API_KEY") or "").strip(),
        "base_url": (
            os.getenv("CALLE_BASE_URL") or "https://api.heycall-e.com"
        ).strip(),
        "phone": (os.getenv("CALLE_TEST_PHONE") or "").strip(),
        "region": (os.getenv("CALLE_TEST_REGION") or "").strip(),
        "locale": (os.getenv("CALLE_TEST_LOCALE") or "").strip(),
        "live_test_confirm": (
            os.getenv("CALLE_LIVE_TEST_CONFIRM") or ""
        ).strip(),
    }


def validate_configuration(configuration: dict[str, str]) -> list[str]:
    errors = []
    phone = configuration["phone"]
    if not phone:
        errors.append("CALLE_TEST_PHONE is missing")
    elif E164_PATTERN.fullmatch(phone) is None:
        errors.append("CALLE_TEST_PHONE must use E.164 format")
    elif not phone.startswith("+33"):
        errors.append("CALLE_TEST_PHONE must be an authorized French +33 number")
    if configuration["region"] != "FR":
        errors.append("CALLE_TEST_REGION must equal FR")
    if configuration["locale"] != "fr-FR":
        errors.append("CALLE_TEST_LOCALE must equal fr-FR")
    if not configuration["api_key"]:
        errors.append("CALLE_API_KEY is missing")
    return errors


def build_models(configuration: dict[str, str]) -> tuple[SourcingRequest, Supplier]:
    now = datetime.now(timezone.utc)
    sourcing_request = SourcingRequest(
        id=REQUEST_ID,
        vehicle_make="Renault",
        vehicle_model="Clio",
        vehicle_year=2019,
        part_name="Alternator",
        requested_reference="TEST-ALT-CLIO-2019-001",
        quantity=1,
        max_budget=Decimal("180.00"),
        currency="EUR",
        needed_by=date.today(),
        status="preflight",
        created_at=now,
        updated_at=now,
    )
    supplier = Supplier(
        id=SUPPLIER_ID,
        name="Authorized French Test Recipient",
        phone_e164=configuration["phone"],
        authorized_for_calls=True,
        created_at=now,
        updated_at=now,
    )
    return sourcing_request, supplier


def build_future_request(configuration: dict[str, str]) -> dict[str, Any]:
    sourcing_request, supplier = build_models(configuration)
    provider = CalleCallProvider(
        api_key=configuration["api_key"],
        base_url=configuration["base_url"],
        recipients={
            supplier.id: {
                "phones": [configuration["phone"]],
                "region": configuration["region"],
                "locale": configuration["locale"],
            }
        },
    )
    return provider.build_quote_request(sourcing_request, supplier)


def validate_sdk_mapping(future_request: dict[str, Any]) -> None:
    inspect.signature(CalleCalls.create).bind(object(), **future_request)


def validate_tls() -> None:
    context = ssl.create_default_context()
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise RuntimeError("TLS certificate verification is not enabled")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    configuration = load_configuration()
    errors = validate_configuration(configuration)
    future_request: dict[str, Any] | None = None
    if not errors:
        try:
            future_request = build_future_request(configuration)
            validate_sdk_mapping(future_request)
            validate_tls()
        except (PermissionError, RuntimeError, ValueError) as exc:
            errors.append(str(exc))

    masked = (
        mask_phone(configuration["phone"])
        if configuration["phone"]
        else "not configured"
    )
    print("SUPPLYSCOUT VOICE — FINAL LIVE CALL PREFLIGHT")
    print(f"\nRecipient: {masked}")
    print("Country: France")
    print(f"Locale: {configuration['locale'] or 'not configured'}")
    print("Purpose: Supplier quote collection")
    print("Reference: TEST-ALT-CLIO-2019-001")
    print("Budget: 180 EUR")
    print(f"Live CALL-E provider ready: {'YES' if not errors else 'NO'}")
    print(f"API key configured: {'YES' if configuration['api_key'] else 'NO'}")
    if future_request is not None:
        print("SDK fields: task, recipient, recipient_result_schema, metadata, idempotency_key")
        print(f"Structured-result fields: {', '.join(CALLE_QUOTE_SCHEMA['properties'])}")
        print(f"Idempotency key: {future_request['idempotency_key']}")
        print(
            "Task: French, consent-first authorized supplier quote collection; "
            "no transaction or commitment"
        )
    if errors:
        print("Preflight errors:")
        for error in errors:
            print(f"- {error}")
    print("\nNO CALL HAS BEEN PLACED")
    print("\nEXPLICIT HUMAN APPROVAL IS REQUIRED BEFORE EXECUTING POST /v1/calls")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
