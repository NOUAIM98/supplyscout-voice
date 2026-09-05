import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.app.providers.calls.calle import CalleCallProvider
from backend.poc.supplyscout_quote_preflight import load_configuration


def main() -> int:
    configuration = load_configuration()
    if not configuration["api_key"]:
        print("CALL-E SDK connectivity: FAILED - CALLE_API_KEY is missing")
        return 2

    provider = CalleCallProvider(
        api_key=configuration["api_key"],
        base_url=configuration["base_url"],
    )
    try:
        for attempt in range(1, 4):
            try:
                result = provider.list_goals(limit=1)
            except Exception as exc:
                cause = exc.__cause__
                underlying = type(cause).__name__ if cause else type(exc).__name__
                print(f"Read-only GET attempt {attempt}: FAILED ({underlying})")
                return 1
            print(
                f"Read-only GET attempt {attempt}: SUCCESS "
                f"(response type: {type(result).__name__})"
            )
    finally:
        provider.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
