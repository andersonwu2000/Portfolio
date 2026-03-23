"""API middleware — audit logging, request tracking."""

from __future__ import annotations

import itertools
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("audit")

# Thread-safe request counter
_counter = itertools.count(1)
_request_count = 0


def get_request_count() -> int:
    return _request_count


class AuditMiddleware(BaseHTTPMiddleware):
    """Log all mutation requests (POST/PUT/DELETE) for audit trail."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        global _request_count
        _request_count = next(_counter)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        # Log mutations
        if request.method in ("POST", "PUT", "DELETE"):
            user = "anonymous"
            if hasattr(request.state, "user"):
                user = request.state.user
            logger.info(
                "AUDIT %s %s -> %d (%.0fms) user=%s ip=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                user,
                request.client.host if request.client else "unknown",
            )

        return response
