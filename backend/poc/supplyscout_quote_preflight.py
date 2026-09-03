import inspect
import os
import re
import ssl
import sys
from pathlib import Path
from typing import Any

from calle.calls import CalleCalls
from dotenv import load_dotenv

from supplyscout_quote_preview import (
    CALL_E_TASK,
    IDEMPOTENCY_KEY,
    SUPPLIER_QUOTE_SCHEMA,
    mask_phone,
)


E164_PATTERN = re.compile(r"\+[1-9]\d{7,14}")


def load_recipient() -> dict[str, Any]:
    backend_dir = Path(__file__).resolve().parents[1]
    load_dotenv(backend_dir / ".env", override=False)
    return {
        "phones": [(os.getenv("CALLE_TEST_PHONE") or "").strip()],
        "region": (os.getenv("CALLE_TEST_REGION") or "").strip(),
        "locale": (os.getenv("CALLE_TEST_LOCALE") or "").strip(),
    }


def validate_recipient(recipient: dict[str, Any]) -> list[str]:
    phone = recipient["phones"][0]
    region = recipient["region"]
    locale = recipient["locale"]
    errors = []
    if not phone:
        errors.append("CALLE_TEST_PHONE is missing")
    elif E164_PATTERN.fullmatch(phone) is None:
        errors.append("CALLE_TEST_PHONE must use E.164 format")
    if not region:
        errors.append("CALLE_TEST_REGION is missing")
    elif region.upper() == "MA":
        errors.append("CALLE_TEST_REGION must not be MA for this test")
    if not locale:
        errors.append("CALLE_TEST_LOCALE is missing")
    return errors


def build_future_request(recipient: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": CALL_E_TASK,
        "recipient": recipient,
        "result_schema": SUPPLIER_QUOTE_SCHEMA,
        "metadata": {
            "workflow_type": "supplier_quote",
            "sourcing_request_ref": "demo-clio-alternator-001",
            "environment": "poc",
        },
        "idempotency_key": IDEMPOTENCY_KEY,
    }


def validate_sdk_mapping(future_request: dict[str, Any]) -> None:
    inspect.signature(CalleCalls.create).bind(object(), **future_request)


def validate_tls() -> None:
    context = ssl.create_default_context()
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise RuntimeError("TLS certificate verification is not enabled")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    recipient = load_recipient()
    errors = validate_recipient(recipient)
    future_request = build_future_request(recipient)
    validate_sdk_mapping(future_request)
    validate_tls()

    phone = recipient["phones"][0]
    print("SUPPLYSCOUT VOICE — LIVE CALL PREFLIGHT")
    print("\nRecipient:")
    print(mask_phone(phone) if phone else "not configured")
    print("\nRegion:")
    print(recipient["region"] or "not configured")
    print("\nLocale:")
    print(recipient["locale"] or "not configured")
    print("\nVehicle:\n2019 Renault Clio")
    print("\nPart:\nAlternator")
    print("\nReference:\nTEST-ALT-CLIO-2019-001")
    print("\nQuantity:\n1")
    print("\nMaximum budget:\n180 EUR")
    print("\nPurpose:\nSupplier quote collection only")
    print("\nCALL-E will be instructed to:")
    print("- identify itself as an AI assistant;")
    print("- confirm exact reference;")
    print("- collect factual quote information;")
    print("- preserve uncertainty;")
    print("- not order;")
    print("- not purchase;")
    print("- not pay;")
    print("- not reserve;")
    print("- not commit.")
    print("\nStructured output fields:")
    for field in SUPPLIER_QUOTE_SCHEMA["required"]:
        print(f"- {field}")
    print(f"\nIdempotency key:\n{future_request['idempotency_key']}")
    print("\nSDK invocation mapping: VALIDATED, NOT EXECUTED")
    print("TLS: SYSTEM TRUST STORE, CERTIFICATE VERIFICATION REQUIRED")
    if errors:
        print("\nPreflight validation: FAILED")
        for error in errors:
            print(f"- {error}")
    else:
        print("\nPreflight validation: PASSED")
    print("\nLIVE CALL NOT STARTED")
    print("EXPLICIT HUMAN APPROVAL REQUIRED BEFORE POST /v1/calls")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
