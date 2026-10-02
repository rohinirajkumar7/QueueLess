"""
Shared slowapi Limiter instance.

Importing from main.py would create a circular import (main imports router,
router would import main). This module breaks the cycle by providing the
limiter as a standalone singleton that both main.py and router.py can import.
"""
from starlette.requests import Request
from slowapi import Limiter
from app.core.config import get_settings


def _get_real_ip(request: Request) -> str:
    """Rate-limit key: honour X-Forwarded-For (first hop only) so requests
    that arrive via a reverse proxy or from k6 with per-VU synthetic IPs are
    bucketed individually.  Falls back to the direct TCP peer address."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # The header may be a comma-separated list; take only the first entry.
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


_settings = get_settings()


class QueueLessLimiter(Limiter):
    def _check_request_limit(
        self,
        request: Request,
        endpoint_func=None,
        in_middleware: bool = True,
    ) -> None:
        # In non-production environments, exempt k6 load tests so concurrency
        # and latency can be measured without hitting low dev rate limits.
        if _settings.environment != "production":
            ua = request.headers.get("user-agent", "")
            if "k6" in ua.lower():
                request.state.view_rate_limit = None
                return
        super()._check_request_limit(request, endpoint_func, in_middleware)


limiter = QueueLessLimiter(
    key_func=_get_real_ip,
    default_limits=[_settings.rate_limit_general],
    storage_uri=_settings.redis_url,
    # Swallow storage errors (e.g. Redis unavailable in CI) so the app
    # degrades gracefully: requests pass through rather than returning 500.
    in_memory_fallback_enabled=True,
)
