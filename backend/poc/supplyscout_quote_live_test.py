import json
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.providers.calls.calle import CalleCallProvider, CalleResultError
from backend.poc.supplyscout_quote_preflight import (
    SUPPLIER_ID,
    build_models,
    load_configuration,
    mask_phone,
    validate_configuration,
)


RESULT_PATH = Path(__file__).resolve().parent / "results" / "calle_quote_test_redacted.json"
RETRY_GUARD_PATH = (
    Path(__file__).resolve().parent
    / "results"
    / "calle_quote_test_retry_1_guard.json"
)
TERMINAL_STATUSES = {
    "completed",
    "failed",
    "no_answer",
    "declined",
    "canceled",
    "cancelled",
    "voicemail",
    "busy",
    "expired",
}
LIVE_TEST_CONFIRMATION = "PLACE_ONE_AUTHORIZED_TEST_CALL"


def live_test_confirmed(configuration: dict[str, str]) -> bool:
    return configuration.get("live_test_confirm") == LIVE_TEST_CONFIRMATION


def redact(value: Any, *, phone: str, api_key: str) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if key.lower() in {"authorization", "api_key", "token", "access_token"}:
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact(item, phone=phone, api_key=api_key)
        return redacted
    if isinstance(value, list):
        return [redact(item, phone=phone, api_key=api_key) for item in value]
    if isinstance(value, str):
        safe = value.replace(phone, mask_phone(phone)) if phone else value
        safe = safe.replace(api_key, "[REDACTED]") if api_key else safe
        return safe
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return value


def save_artifact(data: dict[str, Any], configuration: dict[str, str]) -> None:
    safe = redact(
        data,
        phone=configuration["phone"],
        api_key=configuration["api_key"],
    )
    temporary = RESULT_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(safe, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(RESULT_PATH)


def claim_single_attempt(configuration: dict[str, str]) -> bool:
    RETRY_GUARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    initial = {
        "create_attempted": True,
        "create_attempt_limit": 1,
        "retry_number": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "create_pending",
        "recipient": mask_phone(configuration["phone"]),
    }
    try:
        with RETRY_GUARD_PATH.open("x", encoding="utf-8") as artifact:
            json.dump(initial, artifact, ensure_ascii=False, indent=2)
            artifact.write("\n")
    except FileExistsError:
        return False
    return True


def normalized_quote_dict(quote: Any) -> dict[str, Any]:
    fields = (
        "id",
        "sourcing_request_id",
        "supplier_id",
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
        "created_at",
    )
    return {field: getattr(quote, field) for field in fields}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    configuration = load_configuration()
    if not live_test_confirmed(configuration):
        print("LIVE CALL BLOCKED — explicit local confirmation required")
        return 3
    errors = validate_configuration(configuration)
    if errors:
        print("LIVE CALL SAFETY VALIDATION: FAILED")
        for error in errors:
            print(f"- {error}")
        print("NO CALL HAS BEEN PLACED")
        return 1

    sourcing_request, supplier = build_models(configuration)
    provider = CalleCallProvider(
        api_key=configuration["api_key"],
        base_url=configuration["base_url"],
        recipients={
            SUPPLIER_ID: {
                "phones": [configuration["phone"]],
                "region": "FR",
                "locale": "fr-FR",
            }
        },
    )
    future_request = provider.build_quote_request(sourcing_request, supplier)
    if "Êtes-vous d’accord pour continuer ?" not in future_request["task"]:
        print("LIVE CALL SAFETY VALIDATION: FAILED — consent-first task missing")
        print("NO CALL HAS BEEN PLACED")
        return 1

    masked = mask_phone(configuration["phone"])
    print("SUPPLYSCOUT LIVE CALL — RETRY")
    print(f"\nRecipient: {masked}")
    print("Region: FR")
    print("Locale: fr-FR")
    print("Purpose: Supplier quote test")
    print("Reference: TEST-ALT-CLIO-2019-001")
    print("\nAUTHORIZED LIVE TEST: YES")
    print("Verified CALL-E transport: YES")
    print("Maximum create attempts allowed in this run: 1")
    print(
        "Idempotency key: "
        "supplyscout:quote:demo-clio-alternator-001:test-supplier-001"
    )

    if not claim_single_attempt(configuration):
        print("LIVE CALL ABORTED: the one-call execution guard already exists")
        print("NO ADDITIONAL CALL WAS PLACED")
        return 2

    try:
        response = provider.start_quote_call(sourcing_request, supplier)
    except Exception as exc:
        cause = exc.__cause__
        save_artifact(
            {
                "create_attempted": True,
                "create_attempt_limit": 1,
                "status": "create_failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "underlying_error_type": type(cause).__name__ if cause else None,
                "underlying_error": str(cause) if cause else None,
            },
            configuration,
        )
        print(f"CALL-E creation failed: {type(exc).__name__}: {exc}")
        print("NO RETRY WILL BE ATTEMPTED")
        return 1

    call_id = response.get("id") or response.get("call_id")
    if not isinstance(call_id, str) or not call_id:
        save_artifact(
            {"create_attempted": True, "status": "missing_call_id", "response": response},
            configuration,
        )
        print("CALL-E call ID: unavailable")
        print("NO RETRY WILL BE ATTEMPTED")
        return 1

    print(f"CALL-E call ID: {call_id}")
    current = response
    deadline = time.monotonic() + 600
    while str(current.get("status", "")).lower() not in TERMINAL_STATUSES:
        if time.monotonic() >= deadline:
            save_artifact(
                {
                    "create_attempted": True,
                    "call_id": call_id,
                    "status": "poll_timeout",
                    "call": current,
                },
                configuration,
            )
            print("CALL-E polling timed out after 10 minutes")
            print("NO RETRY WILL BE ATTEMPTED")
            return 1
        print(f"Call status: {current.get('status', 'unknown')}", flush=True)
        time.sleep(10)
        try:
            current = provider.get_call(call_id)
        except Exception as exc:
            save_artifact(
                {
                    "create_attempted": True,
                    "call_id": call_id,
                    "status": "poll_failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "call": current,
                },
                configuration,
            )
            print(f"CALL-E polling failed: {type(exc).__name__}: {exc}")
            print("NO RETRY WILL BE ATTEMPTED")
            return 1

    events: dict[str, Any] | None = None
    events_error: str | None = None
    try:
        events = provider.list_events(call_id, limit=100)
    except Exception as exc:
        events_error = f"{type(exc).__name__}: {exc}"

    normalized: dict[str, Any] | None = None
    normalization_error: str | None = None
    try:
        quote = provider.normalize_quote_response(current, sourcing_request, supplier)
        normalized = normalized_quote_dict(quote)
    except CalleResultError as exc:
        normalization_error = str(exc)

    provider_result = provider.provider_results.get(supplier.id)
    artifact = {
        "create_attempted": True,
        "create_attempt_limit": 1,
        "call_id": call_id,
        "status": current.get("status"),
        "provider_result": provider_result,
        "structured_result": provider._structured_result(current),
        "normalized_quote": normalized,
        "normalization_error": normalization_error,
        "events": events,
        "events_error": events_error,
        "call": current,
    }
    save_artifact(artifact, configuration)

    safe_provider = redact(
        provider_result,
        phone=configuration["phone"],
        api_key=configuration["api_key"],
    )
    safe_structured = redact(
        provider._structured_result(current),
        phone=configuration["phone"],
        api_key=configuration["api_key"],
    )
    safe_normalized = redact(
        normalized,
        phone=configuration["phone"],
        api_key=configuration["api_key"],
    )
    print(f"Terminal status: {current.get('status')}")
    print("Provider result:")
    print(json.dumps(safe_provider, ensure_ascii=False, indent=2, default=str))
    print("Structured result:")
    print(json.dumps(safe_structured, ensure_ascii=False, indent=2, default=str))
    print("SUPPLYSCOUT NORMALIZED QUOTE")
    print(json.dumps(safe_normalized, ensure_ascii=False, indent=2, default=str))
    if normalization_error:
        print(f"Normalization error: {normalization_error}")
    print(f"Transcript/events retrieval: {'available' if events is not None else events_error}")
    print(f"Redacted artifact: {RESULT_PATH}")
    print("NO SECOND CALL WAS PLACED")
    return 0 if normalized is not None else 1


if __name__ == "__main__":
    sys.exit(main())
