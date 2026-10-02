"""
Tests for Task 1: UUID-vs-string bug fix in list_staff() and remove_staff().

Verifies:
- list_staff returns 200 for a user querying their own org
- list_staff returns 403 for a user querying a different org
- remove_staff returns 200 (204/dict) for admin removing staff from their own org
- remove_staff returns 403 for a user targeting a different org's staff endpoint
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password, create_access_token
from app.main import app
from app.models.models import Organization, Role, Service, StaffService, Status, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_org(name: str) -> Organization:
    """Create and persist an Organization; return the ORM object with its id."""
    async with SessionLocal() as db:
        org = Organization(name=name, timezone="UTC", is_test=True)
        db.add(org)
        await db.flush()
        await db.commit()
        await db.refresh(org)
        return org


async def _make_admin(org_id: uuid.UUID, email_prefix: str) -> User:
    async with SessionLocal() as db:
        u = User(
            name="Admin",
            email=f"{email_prefix}-{uuid.uuid4()}@example.com",
            password_hash=hash_password("Secret123!"),
            role=Role.ORG_ADMIN,
            org_id=org_id,
        )
        db.add(u)
        await db.flush()
        await db.commit()
        await db.refresh(u)
        return u


async def _make_staff(org_id: uuid.UUID) -> User:
    async with SessionLocal() as db:
        u = User(
            name="Staff",
            email=f"staff-{uuid.uuid4()}@example.com",
            password_hash=hash_password("Secret123!"),
            role=Role.STAFF,
            org_id=org_id,
        )
        db.add(u)
        await db.flush()
        await db.commit()
        await db.refresh(u)
        return u


async def _cleanup(*user_ids: uuid.UUID, org_ids: list[uuid.UUID] | None = None):
    async with SessionLocal() as db:
        for uid in user_ids:
            u = await db.get(User, uid)
            if u:
                await db.delete(u)
        for oid in (org_ids or []):
            o = await db.get(Organization, oid)
            if o:
                await db.delete(o)
        await db.commit()


def _token(user: User) -> str:
    return create_access_token(str(user.id), user.role.value)


# ---------------------------------------------------------------------------
# list_staff — Task 1 tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_staff_own_org_returns_200():
    """Admin querying their own org's staff list must succeed (200)."""
    org = await _make_org("OrgA-list-staff")
    admin = await _make_admin(org.id, "admin-own")
    staff = await _make_staff(org.id)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(
                f"/api/v1/organizations/{org.id}/staff",
                headers={"Authorization": f"Bearer {_token(admin)}"},
            )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    finally:
        await _cleanup(admin.id, staff.id, org_ids=[org.id])


@pytest.mark.asyncio
async def test_list_staff_different_org_returns_403():
    """Admin querying a different org's staff list must be rejected with 403."""
    org_a = await _make_org("OrgA-list-403")
    org_b = await _make_org("OrgB-list-403")
    admin_a = await _make_admin(org_a.id, "admin-403")

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get(
                f"/api/v1/organizations/{org_b.id}/staff",
                headers={"Authorization": f"Bearer {_token(admin_a)}"},
            )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    finally:
        await _cleanup(admin_a.id, org_ids=[org_a.id, org_b.id])


# ---------------------------------------------------------------------------
# remove_staff — Task 1 tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_staff_own_org_returns_200():
    """Admin removing a staff member from their own org must succeed (200)."""
    org = await _make_org("OrgA-remove-staff")
    admin = await _make_admin(org.id, "admin-rm-own")
    staff = await _make_staff(org.id)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete(
                f"/api/v1/organizations/{org.id}/staff/{staff.id}",
                headers={"Authorization": f"Bearer {_token(admin)}"},
            )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    finally:
        # staff.org_id was set to None by the endpoint so we still clean up by user id
        await _cleanup(admin.id, staff.id, org_ids=[org.id])


@pytest.mark.asyncio
async def test_remove_staff_different_org_returns_403():
    """Admin targeting a different org's staff endpoint must be rejected with 403."""
    org_a = await _make_org("OrgA-remove-403")
    org_b = await _make_org("OrgB-remove-403")
    admin_a = await _make_admin(org_a.id, "admin-rm-403")
    staff_b = await _make_staff(org_b.id)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete(
                f"/api/v1/organizations/{org_b.id}/staff/{staff_b.id}",
                headers={"Authorization": f"Bearer {_token(admin_a)}"},
            )
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    finally:
        await _cleanup(admin_a.id, staff_b.id, org_ids=[org_a.id, org_b.id])
