import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


SUPPLIER_QUOTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "exact_reference_confirmed": {"enum": ["yes", "no", "unknown"]},
        "offered_reference": {"type": ["string", "null"]},
        "in_stock": {"enum": ["yes", "no", "unknown"]},
        "manufacturer_or_brand": {"type": ["string", "null"]},
        "condition": {
            "enum": ["new", "remanufactured", "used", "other", "unknown"]
        },
        "quantity_available": {"type": ["integer", "null"]},
        "unit_price": {"type": ["number", "null"]},
        "currency": {"type": ["string", "null"]},
        "tax_included": {"enum": ["yes", "no", "unknown"]},
        "warranty_months": {"type": ["integer", "null"]},
        "pickup_available_today": {"enum": ["yes", "no", "unknown"]},
        "delivery_eta": {"type": ["string", "null"]},
        "quote_valid_until": {"type": ["string", "null"]},
        "supplier_notes": {"type": ["string", "null"]},
    },
    "required": [
        "exact_reference_confirmed",
        "offered_reference",
        "in_stock",
        "manufacturer_or_brand",
        "condition",
        "quantity_available",
        "unit_price",
        "currency",
        "tax_included",
        "warranty_months",
        "pickup_available_today",
        "delivery_eta",
        "quote_valid_until",
        "supplier_notes",
    ],
}

CALL_E_TASK = """You are an AI assistant calling on behalf of an auto repair shop. Clearly disclose this at the start of the call and explain that the purpose is only to obtain a parts quote.

Ask for one alternator for a 2019 Renault Clio with requested reference TEST-ALT-CLIO-2019-001, required today. Explicitly verify whether that exact reference is available. Collect factual answers for stock availability, manufacturer or brand, condition, quantity available, unit price, currency, whether tax is included, warranty in months, pickup availability today, delivery ETA, quote validity, and supplier notes.

Ask short follow-up questions when an answer is ambiguous. Preserve missing or uncertain information as unknown or null; never guess. If the supplier proposes another reference, record it as offered_reference, but do not set exact_reference_confirmed to yes unless the requested reference itself is explicitly confirmed.

This is quote gathering only. Never purchase, order, reserve, pay, or commit to anything. Do not negotiate beyond the stated maximum budget of 180 EUR. Politely finish after gathering the quote."""

IDEMPOTENCY_KEY = "supplyscout:quote:demo-clio-alternator-001:test-supplier-001"


def mask_phone(phone: str) -> str:
    if len(phone) < 7:
        return "******"
    return f"{phone[:3]}******{phone[-3:]}"


def build_preview() -> dict[str, Any]:
    backend_dir = Path(__file__).resolve().parents[1]
    load_dotenv(backend_dir / ".env", override=False)

    return {
        "task": CALL_E_TASK,
        "recipient": {
            "phone": os.getenv("CALLE_TEST_PHONE") or None,
            "region": os.getenv("CALLE_TEST_REGION") or None,
            "locale": os.getenv("CALLE_TEST_LOCALE") or None,
        },
        "result_schema": SUPPLIER_QUOTE_SCHEMA,
        "metadata": {
            "workflow_type": "supplier_quote",
            "sourcing_request_ref": "demo-clio-alternator-001",
        },
        "idempotency_key": IDEMPOTENCY_KEY,
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    preview = build_preview()
    phone = preview["recipient"]["phone"]

    print("SUPPLYSCOUT VOICE — CALL PREVIEW")
    print("\nVehicle")
    print("  Renault Clio, 2019")
    print("\nPart")
    print("  Alternator")
    print("\nReference")
    print("  TEST-ALT-CLIO-2019-001")
    print("\nQuantity")
    print("  1")
    print("\nBudget")
    print("  Maximum 180 EUR")
    print("\nDeadline")
    print("  Today")
    print("\nPurpose")
    print("  Quote gathering only")
    print("\nSafety constraints")
    print("  No purchase, payment, order, reservation, or commitment")
    print("  Do not negotiate beyond 180 EUR")
    print("  Never guess; preserve unknown or uncertain answers")
    print("  A future test phone must be authorized, E.164 formatted, and in a supported region")
    print("\nStructured fields expected")
    for field in SUPPLIER_QUOTE_SCHEMA["required"]:
        print(f"  - {field}")
    if phone:
        print(f"\nTest phone (masked): {mask_phone(phone)}")
    else:
        print("\nTest phone: not configured")
    print(f"Idempotency key: {preview['idempotency_key']}")
    print("\nDRY RUN — NO CALL WILL BE PLACED")


if __name__ == "__main__":
    main()
