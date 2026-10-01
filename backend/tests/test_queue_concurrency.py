"""
Concurrency tests for queue_service.py.

These exercise the claim made in the README/architecture docs: that
PostgreSQL row locking (`with_for_update()`) and `SKIP LOCKED` make
`join_queue` and `call_next` safe under concurrent access, so that:

  - N customers joining the same queue at the same time each get a
    unique, sequential token number (no duplicates, no gaps, no lost
    updates from the `last_token_number += 1` read-modify-write).

  - N staff members calling "next" on the same queue at the same time
    never pull the same waiting token twice, and every waiting token
    is eventually served exactly once.

Requires a real PostgreSQL database (SKIP LOCKED and true concurrent
connections are not meaningfully testable against SQLite). Point
DATABASE_URL at a disposable database before running, e.g.:

    export DATABASE_URL=postgresql+asyncpg://queueless:queueless@localhost:5432/queueless_test
    alembic upgrade head
    pytest tests/test_queue_concurrency.py -q

Test orgs are created with is_test=True and cleaned up in finally blocks
so they never appear in the customer-facing organization listing.
"""
import asyncio
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select, delete

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.models import (
    Organization, Queue, QueueToken, Role, Service, StaffService, User,
)
from app.services.queue_service import call_next, join_queue

N_CUSTOMERS = 10
N_STAFF_ATTEMPTS = 25  # deliberately more than N_CUSTOMERS to hit the empty-queue path too


async def _make_org_and_service() -> uuid.UUID:
    """
    Create an Organization (is_test=True) and a Service, return service.id.
    The is_test flag prevents this org from appearing in the customer listing.
    """
    async with SessionLocal() as db:
        org = Organization(
            name=f"Concurrency Test Org {uuid.uuid4()}",
            timezone="UTC",
            is_test=True,   # <-- never shown to customers
        )
        db.add(org)
        await db.flush()
        service = Service(
            organization_id=org.id,
            name="Concurrency Test Service",
            code=uuid.uuid4().hex[:6].upper(),
            queue_capacity=N_CUSTOMERS + 5,
        )
        db.add(service)
        await db.flush()
        await db.commit()
        return service.id


async def _cleanup_service(service_id: uuid.UUID) -> None:
    """
    Delete the test service (and its org via CASCADE) after the test.
    Runs unconditionally in finally blocks.
    """
    async with SessionLocal() as db:
        svc = await db.get(Service, service_id)
        if svc:
            org_id = svc.organization_id
            # Delete tokens → queues → staff_services → services → org
            await db.execute(
                delete(QueueToken).where(
                    QueueToken.queue_id.in_(
                        select(Queue.id).where(Queue.service_id == service_id)
                    )
                )
            )
            await db.execute(delete(Queue).where(Queue.service_id == service_id))
            await db.execute(
                delete(StaffService).where(StaffService.service_id == service_id)
            )
            await db.execute(delete(Service).where(Service.id == service_id))
            await db.execute(delete(Organization).where(Organization.id == org_id))
            await db.commit()


async def _new_customer(db):
    user = User(
        name="Concurrency Customer",
        email=f"conc-{uuid.uuid4()}@test.local",
        password_hash=hash_password("Secret123!"),
        role=Role.CUSTOMER,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_concurrent_join_queue_assigns_unique_sequential_tokens():
    """
    N customers hit join_queue for the same service at (as close to)
    the same instant as asyncio allows, each on its own DB connection.
    If the queue row lock / SKIP LOCKED handling were missing or wrong,
    concurrent `last_token_number += 1` read-modify-writes would race
    and produce duplicate or skipped token numbers.
    """
    service_id = await _make_org_and_service()
    try:
        async def join_as_new_customer():
            async with SessionLocal() as db:
                user = await _new_customer(db)
                token, _position = await join_queue(db, service_id, user)
                await db.commit()
                return token.token_number

        token_numbers = await asyncio.gather(
            *[join_as_new_customer() for _ in range(N_CUSTOMERS)]
        )

        assert len(token_numbers) == len(set(token_numbers)), (
            f"duplicate token numbers assigned under concurrency: {token_numbers}"
        )
        assert sorted(token_numbers) == list(range(1, N_CUSTOMERS + 1)), (
            f"token numbers should be exactly 1..{N_CUSTOMERS} with no gaps: "
            f"{sorted(token_numbers)}"
        )
    finally:
        await _cleanup_service(service_id)


@pytest.mark.asyncio
async def test_concurrent_call_next_never_serves_same_token_twice():
    """
    Seed a queue with N waiting tokens, then have more "staff" than
    tokens call call_next() on the same queue concurrently. Correct
    behavior: each waiting token is handed out to exactly one caller,
    every other concurrent caller gets the 404 "No waiting customers"
    HTTPException, and nothing is served twice.
    """
    service_id = await _make_org_and_service()
    try:
        queue_id = None
        async with SessionLocal() as db:
            for _ in range(N_CUSTOMERS):
                user = await _new_customer(db)
                await join_queue(db, service_id, user)
            await db.commit()
            queue_id = await db.scalar(
                select(Queue.id).where(Queue.service_id == service_id)
            )

        async def staff_call_next():
            async with SessionLocal() as db:
                try:
                    token = await call_next(db, queue_id)
                except HTTPException as exc:
                    assert exc.status_code == 404
                    return None
                await db.commit()
                return token.id

        results = await asyncio.gather(
            *[staff_call_next() for _ in range(N_STAFF_ATTEMPTS)]
        )

        served = [token_id for token_id in results if token_id is not None]
        assert len(served) == N_CUSTOMERS, (
            f"expected exactly {N_CUSTOMERS} tokens served, got {len(served)}: {served}"
        )
        assert len(served) == len(set(served)), (
            f"a token was served to more than one staff caller: {served}"
        )
    finally:
        await _cleanup_service(service_id)
