from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from urllib import request


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: manual_input.py <user_id> <amount> <location>")
        return 1

    user_id, amount, location = sys.argv[1], sys.argv[2], sys.argv[3]
    payload = json.dumps(
        {
            "user_id": user_id,
            "amount": float(amount),
            "location": location,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode("utf-8")

    api_base_url = os.environ.get("FRAUD_API_BASE_URL", "http://localhost:8000")

    http_request = request.Request(
        url=f"{api_base_url}/transactions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(http_request, timeout=10) as response:
        print(response.read().decode("utf-8"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
