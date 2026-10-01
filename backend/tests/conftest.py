"""
pytest configuration for QueueLess backend tests.

The concurrency tests require a real PostgreSQL database.
Set DATABASE_URL env var before running, e.g.:

    export DATABASE_URL=postgresql+asyncpg://queueless:queueless@localhost:5432/queueless_test
    alembic upgrade head
    pytest tests/test_queue_concurrency.py -q
"""
import pytest
from app.core.database import engine


def pytest_configure(config):
    # Register the asyncio mode marker consumed by pytest-asyncio
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as async (handled by pytest-asyncio)",
    )


@pytest.fixture(autouse=True)
async def dispose_engine_after_test():
    """
    Ensure the async engine's connection pool is disposed after each test
    so connections tied to a closed test event loop do not leak into
    the next test's event loop.
    """
    yield
    await engine.dispose()
