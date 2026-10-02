"""
Services direct routes: patch_service, delete_service.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.models import Role, Service, Status
from app.schemas.schemas import ServiceCreate, ServiceOut
from app.services.audit_service import audit
from app.api.v1.routers.shared import _cache_delete, _ORG_LIST_KEY, _ORG_SVC_KEY

services = APIRouter()


@services.patch("/services/{service_id}", response_model=ServiceOut)
async def patch_service(
    service_id,
    data: ServiceCreate,
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN)),
):
    s = await db.get(Service, service_id)
    if not s or str(user.org_id) != str(s.organization_id):
        raise HTTPException(404, "Service not found")
    for k, v in data.model_dump().items():
        setattr(s, k, v)
    await audit(db, s.organization_id, user.id, "UPDATE", "Service", s.id)
    await db.commit()
    _cache_delete(_ORG_SVC_KEY.format(org_id=str(s.organization_id)))
    return s


@services.delete("/services/{service_id}")
async def delete_service(
    service_id,
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN)),
):
    s = await db.get(Service, service_id)
    if not s or str(user.org_id) != str(s.organization_id):
        raise HTTPException(404, "Service not found")
    s.status = Status.INACTIVE
    await db.commit()
    _cache_delete(
        _ORG_LIST_KEY,
        _ORG_SVC_KEY.format(org_id=str(s.organization_id)),
    )
    return {"message": "Service deactivated"}
