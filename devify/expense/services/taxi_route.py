"""Keep taxi pickup and dropoff names from attached itineraries."""

import re

AMAP_RIDE = re.compile(
    r"(?:^|\n)\s*\d+\s+.*?\b(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+"
    r"\S+\s+(.+?)\s+(\d+(?:\.\d+)?)元(?=\s|$)",
    re.DOTALL,
)


def parse_amap_itinerary(text: str) -> dict:
    """Read the route columns from a text-layer Amap itinerary."""
    if (
        "高德地图" not in text
        or "行程单" not in text
        or "起点 终点" not in text
    ):
        return {}
    count = re.search(r"共计\s*(\d+)\s*单行程", text)
    if count and int(count.group(1)) != 1:
        return {}
    table = text.split("起点 终点", 1)[1].split("页码：", 1)[0]
    routes = []
    for match in AMAP_RIDE.finditer(table):
        route = " ".join(match.group(2).split())
        origin, separator, destination = route.rpartition(" ")
        if origin and separator and destination:
            routes.append((origin, destination))
    if len(routes) == 1:
        return {
            "from_address": routes[0][0],
            "to_address": routes[0][1],
        }
    # A wrapped column can split a place name across spaces. For multiple
    # rides the plain text cannot reliably separate adjacent route columns.
    return {}


def normalize_route(details: dict) -> dict:
    if not isinstance(details, dict):
        return {}
    result = dict(details)
    for canonical, aliases in (
        ("from_address", ("start_location", "pickup", "from")),
        ("to_address", ("end_location", "dropoff", "to")),
    ):
        if not result.get(canonical):
            value = next(
                (result[key] for key in aliases if result.get(key)), None
            )
            if value:
                result[canonical] = value
        if result.get(canonical):
            for alias in aliases:
                result.pop(alias, None)
    trips = result.get("trips")
    if (
        isinstance(trips, list)
        and len(trips) == 1
        and isinstance(trips[0], dict)
    ):
        if not result.get("from_address") and trips[0].get("from"):
            result["from_address"] = trips[0]["from"]
        if not result.get("to_address") and trips[0].get("to"):
            result["to_address"] = trips[0]["to"]
    return result


def merge_route(primary: dict, itinerary: dict) -> dict:
    result = normalize_route(primary)
    source = normalize_route(itinerary)
    for key in ("from_address", "to_address", "trips", "trip_count"):
        if not result.get(key) and source.get(key):
            result[key] = source[key]
    return result
