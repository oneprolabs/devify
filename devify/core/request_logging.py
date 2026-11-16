"""Request correlation without logging bodies, credentials or query strings."""

import logging
import re
import time
import uuid
from contextvars import ContextVar

_request_id = ContextVar("request_id", default="-")
_valid_id = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
logger = logging.getLogger("core.requests")


def current_request_id():
    return _request_id.get()


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.META.get("HTTP_X_REQUEST_ID", "")
        request_id = (
            supplied if _valid_id.fullmatch(supplied) else uuid.uuid4().hex
        )
        request.request_id = request_id
        token = _request_id.set(request_id)
        started = time.monotonic()
        status = 500
        try:
            response = self.get_response(request)
            status = response.status_code
            response["X-Request-ID"] = request_id
            return response
        finally:
            try:
                # Route templates omit identifiers and query-string values.
                match = getattr(request, "resolver_match", None)
                route = getattr(match, "route", None) or "unmatched"
                duration = round((time.monotonic() - started) * 1000)
                level = logging.ERROR if status >= 500 else logging.INFO
                logger.log(
                    level,
                    "http_request method=%s route=%s status=%s duration_ms=%s",
                    request.method,
                    route,
                    status,
                    duration,
                    extra={
                        "method": request.method,
                        "route": route,
                        "status_code": status,
                        "duration_ms": duration,
                    },
                )
            finally:
                _request_id.reset(token)
