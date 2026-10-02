"""
Tests for Task 3: Rate limiting via slowapi.

Verifies that the login endpoint returns 429 after exceeding the configured
rate limit.
"""
import random
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_login_rate_limit_returns_429():
    """
    After exceeding the rate limit on /auth/login, the endpoint must
    return 429 with a JSON body (not an unhandled exception).
    """
    settings = get_settings()
    # Parse the configured limit, e.g. "5/minute" -> 5 requests allowed
    try:
        limit_count = int(settings.rate_limit_login.split("/")[0])
    except Exception:
        limit_count = 5

    bad_credentials = {"email": "nobody@example.com", "password": "WrongPassword123!"}

    # Generate a unique client IP so each test run is isolated in Redis
    unique_ip = f"10.{random.randint(1, 250)}.{random.randint(1, 250)}.{random.randint(1, 250)}"

    async with AsyncClient(
        transport=ASGITransport(app=app, client=(unique_ip, 12345)),
        base_url="http://test",
    ) as c:
        responses = []
        for _ in range(limit_count + 2):
            r = await c.post("/api/v1/auth/login", json=bad_credentials)
            responses.append(r)

    # Initial requests within limit should return 401 (invalid credentials)
    assert responses[0].status_code == 401, (
        f"Initial request should be 401, got {responses[0].status_code}: {responses[0].text}"
    )

    # The request that exceeds limit must return 429
    last_response = responses[-1]
    assert last_response.status_code == 429, (
        f"Expected 429 after exceeding {limit_count}/minute limit, got {last_response.status_code}: {last_response.text}"
    )

    # Response body must be clean JSON
    body = last_response.json()
    assert "error" in body or "detail" in body or "message" in body, (
        f"429 response should have a JSON error body: {body}"
    )
