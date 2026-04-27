from __future__ import annotations

import math


KNOWN_LOCATIONS: dict[str, tuple[float, float]] = {
    "ankara": (39.9334, 32.8597),
    "antalya": (36.8969, 30.7133),
    "berlin": (52.52, 13.405),
    "bursa": (40.1828, 29.0663),
    "denizli": (37.7765, 29.0864),
    "dubai": (25.2048, 55.2708),
    "erzurum": (39.9043, 41.2679),
    "gaziantep": (37.0662, 37.3833),
    "izmir": (38.4237, 27.1428),
    "istanbul": (41.0082, 28.9784),
    "kayseri": (38.7225, 35.4875),
    "konya": (37.8746, 32.4932),
    "london": (51.5072, -0.1276),
    "new york": (40.7128, -74.006),
    "paris": (48.8566, 2.3522),
    "san francisco": (37.7749, -122.4194),
    "trabzon": (41.0015, 39.7178),
}


def normalize_location(location: str) -> str:
    return " ".join(location.strip().lower().split())


def get_coordinates(location: str) -> tuple[float, float] | None:
    return KNOWN_LOCATIONS.get(normalize_location(location))


def haversine_km(origin: tuple[float, float], destination: tuple[float, float]) -> float:
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius_km = 6371.0

    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def is_impossible_travel(
    previous_location: str,
    current_location: str,
    elapsed_hours: float,
    max_speed_kmh: float,
) -> tuple[bool, float | None]:
    if elapsed_hours <= 0:
        return False, None

    previous_coordinates = get_coordinates(previous_location)
    current_coordinates = get_coordinates(current_location)

    if previous_coordinates is None or current_coordinates is None:
        return False, None

    distance = haversine_km(previous_coordinates, current_coordinates)
    required_hours = distance / max_speed_kmh if max_speed_kmh > 0 else float("inf")
    return elapsed_hours < required_hours, distance
