"""
Organization routes: list, get, create, patch, delete orgs; list/create/delete staff.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete

from app.api.deps import current_user, require_roles
from app.core.database import get_db
from app.core.security import hash_password
from app.models.models import Organization, Role, Service, StaffService, Status, User
from app.schemas.schemas import OrgCreate, OrgOut, ServiceCreate, ServiceOut, StaffCreate, UserOut
from app.services.audit_service import audit
from app.api.v1.routers.shared import (
    _cache_delete,
    _cache_get,
    _cache_set,
    _ORG_LIST_KEY,
    _ORG_SVC_KEY,
)

log = logging.getLogger("queueless.router.orgs")

orgs = APIRouter(prefix="/organizations", tags=["organizations"])


@orgs.get("", response_model=list[OrgOut])
async def list_orgs(db=Depends(get_db)):
    """
    Return active, non-test organizations.
    Result is cached in Redis for 45 s and invalidated when orgs change.
    """
    cached = _cache_get(_ORG_LIST_KEY)
    if cached is not None:
        return cached

    rows = (
        await db.scalars(
            select(Organization)
            .where(Organization.status == Status.ACTIVE, Organization.is_test == False)
            .order_by(Organization.name)
        )
    ).all()

    result = [OrgOut.model_validate(o).model_dump(mode="json") for o in rows]
    _cache_set(_ORG_LIST_KEY, result)
    return rows


@orgs.get("/mine", response_model=OrgOut)
async def get_my_org(db=Depends(get_db), user=Depends(require_roles(Role.ORG_ADMIN))):
    if not user.org_id:
        raise HTTPException(409, "Your organization admin account is not linked to an organization")
    org = await db.get(Organization, user.org_id)
    if not org or org.status != Status.ACTIVE:
        raise HTTPException(404, "Your organization was not found or is inactive")
    return org


@orgs.get("/{org_id}", response_model=OrgOut)
async def get_org(org_id, db=Depends(get_db)):
    o = await db.get(Organization, org_id)
    if not o:
        raise HTTPException(404, "Organization not found")
    return o


@orgs.post("", response_model=OrgOut)
async def create_org(
    data: OrgCreate,
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN)),
):
    o = Organization(**data.model_dump())
    db.add(o)
    await db.flush()
    user.org_id = o.id
    await audit(db, o.id, user.id, "CREATE", "Organization", o.id)
    await db.commit()
    _cache_delete(_ORG_LIST_KEY)
    return o


@orgs.patch("/{org_id}", response_model=OrgOut)
async def patch_org(
    org_id,
    data: OrgCreate,
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN)),
):
    o = await db.get(Organization, org_id)
    if not o or str(user.org_id) != str(o.id):
        raise HTTPException(404, "Organization not found")
    for k, v in data.model_dump().items():
        setattr(o, k, v)
    await audit(db, o.id, user.id, "UPDATE", "Organization", o.id)
    await db.commit()
    _cache_delete(_ORG_LIST_KEY)
    return o


@orgs.delete("/{org_id}")
async def delete_org(
    org_id,
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN)),
):
    o = await db.get(Organization, org_id)
    if not o or str(user.org_id) != str(o.id):
        raise HTTPException(404, "Organization not found")
    o.status = Status.INACTIVE
    await db.commit()
    _cache_delete(_ORG_LIST_KEY)
    return {"message": "Organization deactivated"}


@orgs.get("/{org_id}/services", response_model=list[ServiceOut])
async def list_services(org_id, db=Depends(get_db)):
    """Active services for an org, cached per org (TTL 45 s)."""
    cache_key = _ORG_SVC_KEY.format(org_id=org_id)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    rows = (
        await db.scalars(
            select(Service).where(
                Service.organization_id == org_id,
                Service.status == Status.ACTIVE,
            )
        )
    ).all()

    result = [ServiceOut.model_validate(s).model_dump(mode="json") for s in rows]
    _cache_set(cache_key, result)
    return rows


@orgs.post("/{org_id}/services", response_model=ServiceOut)
async def create_service(
    org_id,
    data: ServiceCreate,
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN)),
):
    if not user.org_id:
        raise HTTPException(409, "Your organization admin account is not linked to an organization")
    if str(user.org_id) != str(org_id):
        raise HTTPException(403, "You can only manage your own organization")
    if not await db.get(Organization, org_id):
        raise HTTPException(404, "Organization not found")
    clean_name = data.name.strip()
    clean_code = data.code.strip().upper()
    if not clean_name:
        raise HTTPException(422, "Service name is required")
    duplicate = await db.scalar(
        select(Service).where(
            Service.organization_id == org_id,
            Service.code == clean_code,
            Service.status == Status.ACTIVE,
        )
    )
    if duplicate:
        raise HTTPException(409, f"A service with code {clean_code} already exists in this organization")
    payload = data.model_dump()
    payload.update(name=clean_name, code=clean_code)
    s = Service(organization_id=org_id, **payload)
    db.add(s)
    await db.flush()
    await audit(db, org_id, user.id, "CREATE", "Service", s.id)
    await db.commit()
    _cache_delete(_ORG_SVC_KEY.format(org_id=org_id))
    return s


@orgs.get("/{org_id}/staff", response_model=list[UserOut])
async def list_staff(
    org_id,
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN)),
):
    if str(user.org_id) != str(org_id):
        raise HTTPException(403, "Organization access denied")
    return (
        await db.scalars(
            select(User)
            .where(User.org_id == org_id, User.role == Role.STAFF)
            .order_by(User.name)
        )
    ).all()


@orgs.post("/{org_id}/staff", response_model=UserOut)
async def create_staff(
    org_id,
    data: StaffCreate,
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN)),
):
    if not user.org_id:
        raise HTTPException(409, "Your organization admin account is not linked to an organization")
    if str(user.org_id) != str(org_id):
        raise HTTPException(403, "You can only manage staff in your own organization")
    if await db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Email already registered")
    if not data.service_ids:
        raise HTTPException(422, "Assign at least one service to the staff member")
    services = (
        await db.scalars(
            select(Service).where(
                Service.id.in_(data.service_ids),
                Service.organization_id == org_id,
                Service.status == Status.ACTIVE,
            )
        )
    ).all()
    if len(services) != len(set(data.service_ids)):
        raise HTTPException(422, "One or more selected services do not belong to this organization")
    staff = User(
        name=data.name.strip(),
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        role=Role.STAFF,
        org_id=org_id,
    )
    db.add(staff)
    await db.flush()
    for service_id in data.service_ids:
        db.add(StaffService(staff_id=staff.id, service_id=service_id))
    await audit(db, org_id, user.id, "CREATE", "User", staff.id)
    await db.commit()
    return staff


@orgs.delete("/{org_id}/staff/{staff_id}")
async def remove_staff(
    org_id,
    staff_id,
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN)),
):
    if str(user.org_id) != str(org_id):
        raise HTTPException(403, "Organization access denied")
    staff = await db.get(User, staff_id)
    if not staff or str(staff.org_id) != str(org_id) or staff.role != Role.STAFF:
        raise HTTPException(404, "Staff member not found")
    await db.execute(delete(StaffService).where(StaffService.staff_id == staff.id))
    staff.org_id = None
    await audit(db, org_id, user.id, "REMOVE", "User", staff.id)
    await db.commit()
    return {"message": "Staff member removed from organization"}
