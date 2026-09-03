import os
import ssl
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


OFFICIAL_BASE_URL = "https://api.heycall-e.com"


def main() -> int:
    backend_dir = Path(__file__).resolve().parents[1]
    load_dotenv(backend_dir / ".env", override=False)

    api_key = os.getenv("CALLE_API_KEY")
    base_url = os.getenv("CALLE_BASE_URL", OFFICIAL_BASE_URL).rstrip("/")

    if not api_key:
        print("CALL-E authentication: ERROR - CALLE_API_KEY is missing")
        return 2
    if base_url != OFFICIAL_BASE_URL:
        print("CALL-E authentication: ERROR - CALLE_BASE_URL is not the official API URL")
        return 2

    try:
        with httpx.Client(
            verify=ssl.create_default_context(),
            timeout=httpx.Timeout(10.0, connect=5.0),
        ) as client:
            response = client.get(
                f"{base_url}/v1/goals",
                headers={"Authorization": f"Bearer {api_key}"},
            )
    except httpx.TimeoutException:
        print("CALL-E authentication: ERROR - request timed out")
        return 3
    except httpx.RequestError as exc:
        print(f"CALL-E authentication: ERROR - connection failed ({type(exc).__name__})")
        return 3

    print(f"HTTP status: {response.status_code}")
    if 200 <= response.status_code < 300:
        print("CALL-E authentication: OK")
        try:
            payload = response.json()
        except ValueError:
            print("Response top-level type: non-JSON")
        else:
            print(f"Response top-level type: {type(payload).__name__}")
            if isinstance(payload, dict):
                print(f"Response top-level keys: {', '.join(sorted(payload))}")
        return 0
    if response.status_code == 401:
        print("CALL-E authentication: FAILED - API key was not accepted")
    elif response.status_code == 403:
        print("CALL-E authentication: FAILED - permission or access denied")
    else:
        print("CALL-E authentication: FAILED - unexpected HTTP response")
    return 1


if __name__ == "__main__":
    sys.exit(main())
