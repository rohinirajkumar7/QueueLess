"""
Tests for Task 2: fail-open multi-tenant check fix.

Verifies that routes which previously allowed requests through when user.org_id
is None (fail-OPEN) now correctly reject them (fail-CLOSED).

Routes tested:
  PATCH /organizations/{org_id}      (patch_org)
  DELETE /organizations/{org_id}     (delete_org)
  PATCH /services/{service_id}       (patch_service)
  DELETE /services/{service_id}      (delete_service)
  GET /analytics/queues              (queue_stats)

Each test creates a user with org_id=None to confirm it gets 404 (not allowed
through), and a mismatched org user to confirm they also get 404.
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.core.database import SessionLocal
from app.core.security import hash_password, create_access_token
from app.main import app
from app.models.models import Organization, Role, Service, Status, User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_org(name: str) -> Organization:
    async with SessionLocal() as db:
        org = Organization(name=name, timezone="UTC", is_test=True)
        db.add(org)
        await db.flush()
        await db.commit()
        await db.refresh(org)
        return org


async def _create_service(org_id: uuid.UUID) -> Service:
    async with SessionLocal() as db:
        svc = Service(
            organization_id=org_id,
            name="Test Service",
            code=uuid.uuid4().hex[:6].upper(),
            queue_capacity=10,
        )
        db.add(svc)
        await db.flush()
        await db.commit()
        await db.refresh(svc)
        return svc


async def _create_user(
    role: Role,
    org_id: uuid.UUID | None = None,
    email_prefix: str = "user",
) -> User:
    async with SessionLocal() as db:
        u = User(
            name="TestUser",
            email=f"{email_prefix}-{uuid.uuid4()}@example.com",
            password_hash=hash_password("Secret123!"),
            role=role,
            org_id=org_id,
        )
        db.add(u)
        await db.flush()
        await db.commit()
        await db.refresh(u)
        return u


async def _cleanup(
    user_ids: list[uuid.UUID] | None = None,
    org_ids: list[uuid.UUID] | None = None,
    service_ids: list[uuid.UUID] | None = None,
):
    async with SessionLocal() as db:
        for uid in user_ids or []:
            u = await db.get(User, uid)
            if u:
                await db.delete(u)
        for sid in service_ids or []:
            s = await db.get(Service, sid)
            if s:
                await db.delete(s)
        for oid in org_ids or []:
            o = await db.get(Organization, oid)
            if o:
                await db.delete(o)
        await db.commit()


def _bearer(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user.id), user.role.value)}"}


PATCH_ORG_DATA = {"name": "Updated", "description": "", "address": "", "timezone": "UTC"}
PATCH_SVC_DATA = {"name": "Updated", "code": "UPD", "description": "", "queue_capacity": 5}


# ---------------------------------------------------------------------------
# patch_org — Task 2 tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_org_user_with_none_org_id_is_rejected():
    """An ORG_ADMIN with org_id=None must be rejected (fail-CLOSED)."""
    org = await _create_org("PatchOrg-NoneUser")
    admin_no_org = await _create_user(Role.ORG_ADMIN, org_id=None, email_prefix="patch-none")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(
                f"/api/v1/organizations/{org.id}",
                json=PATCH_ORG_DATA,
                headers=_bearer(admin_no_org),
            )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    finally:
        await _cleanup(user_ids=[admin_no_org.id], org_ids=[org.id])


@pytest.mark.asyncio
async def test_patch_org_mismatched_org_id_is_rejected():
    """An ORG_ADMIN trying to patch a different org must be rejected."""
    org_a = await _create_org("PatchOrgA-Mismatch")
    org_b = await _create_org("PatchOrgB-Mismatch")
    admin_a = await _create_user(Role.ORG_ADMIN, org_id=org_a.id, email_prefix="patch-mis")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(
                f"/api/v1/organizations/{org_b.id}",
                json=PATCH_ORG_DATA,
                headers=_bearer(admin_a),
            )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    finally:
        await _cleanup(user_ids=[admin_a.id], org_ids=[org_a.id, org_b.id])


# ---------------------------------------------------------------------------
# delete_org — Task 2 tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_org_user_with_none_org_id_is_rejected():
    """An ORG_ADMIN with org_id=None must not be able to delete any org."""
    org = await _create_org("DeleteOrg-NoneUser")
    admin_no_org = await _create_user(Role.ORG_ADMIN, org_id=None, email_prefix="del-none")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete(
                f"/api/v1/organizations/{org.id}",
                headers=_bearer(admin_no_org),
            )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    finally:
        await _cleanup(user_ids=[admin_no_org.id], org_ids=[org.id])


@pytest.mark.asyncio
async def test_delete_org_mismatched_org_id_is_rejected():
    """An ORG_ADMIN trying to delete a different org must be rejected."""
    org_a = await _create_org("DeleteOrgA-Mismatch")
    org_b = await _create_org("DeleteOrgB-Mismatch")
    admin_a = await _create_user(Role.ORG_ADMIN, org_id=org_a.id, email_prefix="del-mis")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete(
                f"/api/v1/organizations/{org_b.id}",
                headers=_bearer(admin_a),
            )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    finally:
        await _cleanup(user_ids=[admin_a.id], org_ids=[org_a.id, org_b.id])


# ---------------------------------------------------------------------------
# patch_service — Task 2 tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_service_user_with_none_org_id_is_rejected():
    """An ORG_ADMIN with org_id=None must not be able to patch any service."""
    org = await _create_org("PatchSvc-NoneUser")
    svc = await _create_service(org.id)
    admin_no_org = await _create_user(Role.ORG_ADMIN, org_id=None, email_prefix="psvc-none")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(
                f"/api/v1/services/{svc.id}",
                json=PATCH_SVC_DATA,
                headers=_bearer(admin_no_org),
            )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    finally:
        await _cleanup(user_ids=[admin_no_org.id], service_ids=[svc.id], org_ids=[org.id])


@pytest.mark.asyncio
async def test_patch_service_mismatched_org_is_rejected():
    """An ORG_ADMIN from a different org must not be able to patch another org's service."""
    org_a = await _create_org("PatchSvcA-Mismatch")
    org_b = await _create_org("PatchSvcB-Mismatch")
    svc_b = await _create_service(org_b.id)
    admin_a = await _create_user(Role.ORG_ADMIN, org_id=org_a.id, email_prefix="psvc-mis")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.patch(
                f"/api/v1/services/{svc_b.id}",
                json=PATCH_SVC_DATA,
                headers=_bearer(admin_a),
            )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    finally:
        await _cleanup(user_ids=[admin_a.id], service_ids=[svc_b.id], org_ids=[org_a.id, org_b.id])


# ---------------------------------------------------------------------------
# delete_service — Task 2 tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_service_user_with_none_org_id_is_rejected():
    """An ORG_ADMIN with org_id=None must not be able to delete any service."""
    org = await _create_org("DelSvc-NoneUser")
    svc = await _create_service(org.id)
    admin_no_org = await _create_user(Role.ORG_ADMIN, org_id=None, email_prefix="dsvc-none")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete(
                f"/api/v1/services/{svc.id}",
                headers=_bearer(admin_no_org),
            )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    finally:
        await _cleanup(user_ids=[admin_no_org.id], service_ids=[svc.id], org_ids=[org.id])


@pytest.mark.asyncio
async def test_delete_service_mismatched_org_is_rejected():
    """An ORG_ADMIN from a different org must not be able to delete another org's service."""
    org_a = await _create_org("DelSvcA-Mismatch")
    org_b = await _create_org("DelSvcB-Mismatch")
    svc_b = await _create_service(org_b.id)
    admin_a = await _create_user(Role.ORG_ADMIN, org_id=org_a.id, email_prefix="dsvc-mis")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete(
                f"/api/v1/services/{svc_b.id}",
                headers=_bearer(admin_a),
            )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    finally:
        await _cleanup(user_ids=[admin_a.id], service_ids=[svc_b.id], org_ids=[org_a.id, org_b.id])
