import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID

import pytest
from django.http import HttpResponse
from django.test import Client, RequestFactory, override_settings
from django.urls import path

from core.request_logging import RequestIdMiddleware, current_request_id
from core.settings.logging_config import TaskIdFormatter


def probe(request):
    logging.getLogger("core.probe").warning("probe")
    return HttpResponse(request.request_id)


def broken(request):
    raise ValueError("probe failure")


urlpatterns = [path("probe", probe), path("broken", broken)]


@pytest.mark.parametrize("supplied", ["", "bad id", "a" * 81, "id\ninjection"])
def test_missing_or_invalid_id_is_replaced(supplied):
    request = RequestFactory().get("/probe", HTTP_X_REQUEST_ID=supplied)
    response = RequestIdMiddleware(probe)(request)
    UUID(response["X-Request-ID"])
    assert response.content.decode() == response["X-Request-ID"]
    assert current_request_id() == "-"


@override_settings(ROOT_URLCONF=__name__)
def test_id_reaches_view_logs_response_and_http_summary(caplog):
    with caplog.at_level(logging.INFO):
        response = Client().get(
            "/probe?secret=do-not-log", HTTP_X_REQUEST_ID="desktop-123"
        )
    assert response["X-Request-ID"] == "desktop-123"
    records = [r for r in caplog.records if r.name.startswith("core.")]
    assert records
    assert all(r.request_id == "desktop-123" for r in records)
    summary = next(r for r in records if r.name == "core.requests")
    assert summary.status_code == 200
    assert summary.route == "probe"
    assert summary.duration_ms >= 0
    assert "do-not-log" not in caplog.text
    assert current_request_id() == "-"


@override_settings(ROOT_URLCONF=__name__)
def test_error_response_still_has_id_and_clears_context():
    response = Client(raise_request_exception=False).get(
        "/broken", HTTP_X_REQUEST_ID="failed-123"
    )
    assert response.status_code == 500
    assert response["X-Request-ID"] == "failed-123"
    assert current_request_id() == "-"


def test_exception_clears_context():
    request = RequestFactory().get("/broken")
    with pytest.raises(ValueError):
        RequestIdMiddleware(broken)(request)
    assert current_request_id() == "-"


def test_concurrent_requests_do_not_share_ids():
    barrier = Barrier(2)

    def run(request_id):
        def view(request):
            barrier.wait(timeout=5)
            return HttpResponse(current_request_id())

        request = RequestFactory().get("/probe", HTTP_X_REQUEST_ID=request_id)
        response = RequestIdMiddleware(view)(request)
        assert current_request_id() == "-"
        return response.content.decode()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, ["first-123", "second-456"])) == [
            "first-123",
            "second-456",
        ]


def test_formatter_outside_request_uses_placeholder():
    record = logging.LogRecord("test", logging.INFO, "", 0, "ok", (), None)
    formatter = TaskIdFormatter("[request_id=%(request_id)s] %(message)s")
    assert formatter.format(record) == "[request_id=-] ok"
