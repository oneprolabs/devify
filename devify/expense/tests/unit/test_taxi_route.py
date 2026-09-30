"""Taxi routes survive the itinerary and invoice being read in either order."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from expense.services.decoder import DecodedSource, DecodeMode
from expense.services.extractor import extract
from expense.services.taxi_route import (
    merge_route,
    normalize_route,
    parse_amap_pdf_route,
)


def test_aliases_from_existing_itineraries_become_visible_route():
    assert normalize_route(
        {"start_location": "北京南站", "end_location": "安苑北里"}
    ) == {
        "from_address": "北京南站",
        "to_address": "安苑北里",
    }


def test_itinerary_fills_only_missing_invoice_route():
    assert merge_route(
        {"from_address": "已核对的起点"},
        {"from_address": "行程单起点", "to_address": "行程单终点"},
    ) == {
        "from_address": "已核对的起点",
        "to_address": "行程单终点",
    }


def test_multiple_rides_remain_separate():
    trips = [
        {"from": "机场", "to": "酒店"},
        {"from": "酒店", "to": "车站"},
    ]
    assert merge_route({}, {"trips": trips}) == {"trips": trips}


def test_amap_pdf_columns_keep_wrapped_destination_together():
    text = (
        "高德地图—打车——行程单\n"
        "共计1单行程\n"
        "序号 服务商 车型 上车时间 城市 起点 终点 金额\n"
    )
    page = MagicMock()
    page.get_size.return_value = (595, 842)
    textpage = page.get_textpage.return_value
    indexes = {"起点": 1, "终点": 2, "金额": 3}
    textpage.search.side_effect = lambda label: SimpleNamespace(
        get_next=lambda: (indexes[label], 2), close=lambda: None
    )
    textpage.get_charbox.side_effect = lambda index: {
        1: (379, 522, 387, 530),
        2: (456, 522, 464, 530),
        3: (521, 522, 529, 530),
    }[index]
    textpage.get_text_bounded.side_effect = [
        "唐人街购物中心(北门)",
        "国家会议中\r\n心2期(7号门)",
    ]

    assert parse_amap_pdf_route([page], text) == {
        "from_address": "唐人街购物中心(北门)",
        "to_address": "国家会议中心2期(7号门)",
    }


def test_amap_multi_ride_text_does_not_guess_wrapped_columns():
    text = (
        "高德地图—打车——行程单\n"
        "共计2单行程\n"
        "序号 服务商 车型 上车时间 城市 起点 终点 金额\n"
        "1 火箭出行 优享型 2026-09-03 08:33 北京市 唐人街购物中心(北门) 国家会议中\n"
        "心2期(6号门) 19.51元\n"
        "2 火箭出行 经济型 2026-09-09 06:22 北京市 HEME HOTEL 北京南站 56.93元\n"
        "页码： 1 / 1"
    )
    assert parse_amap_pdf_route([], text) == {}


def test_extraction_uses_text_layer_when_model_omits_route():
    decoded = DecodedSource(
        mode=DecodeMode.TEXT,
        text=(
            "高德地图—打车——行程单\n"
            "序号 服务商 车型 上车时间 城市 起点 终点 金额\n"
            "1 T3出行 经济型 2026-09-14 14:50 上海市 "
            "T2-P7停车库-D区 101办公中心 69.97元\n"
            "页码： 1 / 1"
        ),
        route_details={
            "from_address": "T2-P7停车库-D区",
            "to_address": "101办公中心",
        },
    )
    raw = {
        "is_invoice": True,
        "invoice_type": "taxi",
        "category": "transport_local",
        "ticket_details": {"service_type": "网约车"},
    }
    email = SimpleNamespace(subject="行程单", sender="高德", received_at=None)
    with patch("expense.services.extractor.call_model", return_value=raw):
        result = extract(decoded, email, "行程单.pdf", "unused", "test")

    assert result["ticket_details"] == {
        "service_type": "网约车",
        "from_address": "T2-P7停车库-D区",
        "to_address": "101办公中心",
    }
