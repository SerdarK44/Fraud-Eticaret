from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime, timezone
from urllib import request


CITIES = [
    "Istanbul",
    "Ankara",
    "Izmir",
    "Antalya",
    "Trabzon",
    "Berlin",
    "London",
    "Dubai",
]


def send_transaction(api_base_url: str, payload: dict) -> None:
    http_request = request.Request(
        url=f"{api_base_url}/transactions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(http_request, timeout=10) as response:
        response.read()


def build_payload(
    user_id: str,
    baseline_amount: float,
    last_location: str,
    anomaly_mode: str | None,
) -> tuple[dict, str]:
    amount = round(random.uniform(baseline_amount * 0.7, baseline_amount * 1.3), 2)
    location = last_location

    if anomaly_mode == "jump":
        amount = round(baseline_amount * random.uniform(4.0, 6.0), 2)
        location = random.choice([city for city in CITIES if city != last_location])
    elif anomaly_mode == "burst":
        amount = round(baseline_amount * random.uniform(3.5, 5.0), 2)
        location = random.choice(CITIES)

    return (
        {
            "user_id": user_id,
            "amount": amount,
            "location": location,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
        location,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Feed random transactions into the fraud API.")
    parser.add_argument("--duration", type=int, default=30, help="How long the script should run.")
    parser.add_argument("--rate", type=int, default=4, help="Requests to send per second.")
    parser.add_argument(
        "--anomaly-chance",
        type=int,
        default=25,
        help="Chance of generating anomaly scenarios as a percentage.",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=12,
        help="How many synthetic users to rotate through.",
    )
    parser.add_argument(
        "--api-base-url",
        default="http://localhost:8000",
        help="Target Fraud Sentinel API base URL.",
    )
    args = parser.parse_args()

    users = [f"user-{index:03d}" for index in range(1, args.users + 1)]
    baselines = {user_id: random.uniform(100, 1200) for user_id in users}
    last_locations = {user_id: random.choice(CITIES) for user_id in users}
    burst_budget = {user_id: 0 for user_id in users}

    end_time = time.time() + args.duration
    sent = 0
    failed = 0

    while time.time() < end_time:
        second_start = time.time()
        for _ in range(args.rate):
            user_id = random.choice(users)
            anomaly_mode = None

            if burst_budget[user_id] > 0:
                anomaly_mode = "burst"
                burst_budget[user_id] -= 1
            elif random.randint(1, 100) <= args.anomaly_chance:
                anomaly_mode = random.choice(["jump", "burst"])
                if anomaly_mode == "burst":
                    burst_budget[user_id] = random.randint(5, 7)

            payload, new_location = build_payload(
                user_id,
                baselines[user_id],
                last_locations[user_id],
                anomaly_mode,
            )

            try:
                send_transaction(args.api_base_url, payload)
                last_locations[user_id] = new_location
                sent += 1
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"Request failed for {user_id}: {exc}")

        elapsed = time.time() - second_start
        time.sleep(max(0, 1 - elapsed))

    print(
        json.dumps(
            {
                "sent": sent,
                "failed": failed,
                "duration_seconds": args.duration,
                "rate": args.rate,
                "anomaly_chance": args.anomaly_chance,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
