"""Keep taxi pickup and dropoff names from attached itineraries."""

import re


def parse_amap_pdf_route(document, text: str) -> dict:
    """Read a single Amap ride from the PDF's printed route columns."""
    if (
        "高德地图" not in text
        or "行程单" not in text
        or "起点 终点" not in text
    ):
        return {}
    count = re.search(r"共计\s*(\d+)\s*单行程", text)
    if not count or int(count.group(1)) != 1 or not len(document):
        return {}

    page = document[0]
    width, height = page.get_size()
    if not (575 <= width <= 615 and 820 <= height <= 860):
        page.close()
        return {}
    textpage = page.get_textpage()
    try:
        boxes = []
        for label in ("起点", "终点", "金额"):
            search = textpage.search(label)
            try:
                match = search.get_next()
            finally:
                search.close()
            if not match:
                return {}
            boxes.append(textpage.get_charbox(match[0]))
        origin_box, destination_box, amount_box = boxes
        if not (
            365 <= origin_box[0] <= 395
            and 440 <= destination_box[0] <= 470
            and 505 <= amount_box[0] <= 535
        ):
            return {}
        bottom = origin_box[1] - 84
        top = origin_box[1] - 3
        boundary = destination_box[0] - 29

        def column(left, right):
            value = textpage.get_text_bounded(
                left=left, bottom=bottom, right=right, top=top
            )
            joined = "".join(line.strip() for line in value.splitlines())
            return joined.replace("\x02", "-").replace("\ufffe", "-")

        origin = column(origin_box[0] - 31, boundary)
        destination = column(boundary + 1, amount_box[0] - 12)
        if origin and destination:
            return {"from_address": origin, "to_address": destination}
        return {}
    finally:
        textpage.close()
        page.close()


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
