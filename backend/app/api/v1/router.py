"""
FastAPI router for QueueLess API v1.

Changes from the original:
- GET /organizations: filters is_test=false so load-test orgs never appear
  to customers.  Results are Redis-cached (TTL 45 s) and invalidated on
  create / update / deactivate of an org or service.
- GET /organizations/{org_id}/services: Redis-cached per org (TTL 45 s),
  invalidated on service create / update / deactivate.
- All other routes are behaviorally identical to the original.
"""
import json
import logging
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import redis as redis_sync
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import error_response
from app.core.security import decode_token, create_access_token, create_refresh_token, hash_password
from app.models.models import (
    Appointment, AppointmentStatus, AuditLog, Notification, NotificationStatus,
    Organization, PasswordResetToken, Queue, QueueToken, Role, Service,
    StaffService, Status, TokenStatus, User,
)
from app.schemas.schemas import (
    AnalyticsOut, AppointmentCreate, AppointmentOut, ForgotPasswordIn,
    JoinOut, LoginIn, NotificationOut, OrgCreate, OrgOut, OrganizationRegisterIn,
    QueueOut, RegisterIn, ResetPasswordIn, ServiceCreate, ServiceOut,
    StaffCreate, TokenOut, TokenOutDetail, UserOut,
)
from app.services.appointment_service import create_appointment
from app.services.audit_service import audit
from app.services.auth_service import register, login
from app.services.email_service import send_email
from app.services.queue_service import join_queue, queue_snapshot, call_next, transition
from app.websocket.events import publish_queue_state
from app.workers.tasks import send_notification_email

log = logging.getLogger("queueless.router")

# ---------------------------------------------------------------------------
# Redis client (sync — used only for cache get/set, not for Celery)
# ---------------------------------------------------------------------------
_settings = get_settings()
try:
    _redis = redis_sync.from_url(_settings.redis_url, decode_responses=True)
except Exception:
    _redis = None  # gracefully degrade if Redis unavailable

_CACHE_TTL = 45  # seconds
_ORG_LIST_KEY = "cache:orgs:list"
_ORG_SVC_KEY = "cache:org:{org_id}:services"


def _cache_get(key: str):
    try:
        if _redis:
            raw = _redis.get(key)
            if raw:
                return json.loads(raw)
    except Exception:
        pass
    return None


def _cache_set(key: str, value, ttl: int = _CACHE_TTL):
    try:
        if _redis:
            _redis.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


def _cache_delete(*keys: str):
    try:
        if _redis and keys:
            _redis.delete(*keys)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/v1")
auth = APIRouter(prefix="/auth", tags=["auth"])
orgs = APIRouter(prefix="/organizations", tags=["organizations"])
queues = APIRouter(prefix="", tags=["queues"])
appointments = APIRouter(prefix="/appointments", tags=["appointments"])
analytics = APIRouter(prefix="/analytics", tags=["analytics"])
users = APIRouter(prefix="", tags=["users"])


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@auth.post("/register", response_model=UserOut)
async def register_ep(data: RegisterIn, db=Depends(get_db)):
    u = await register(db, data)
    await db.commit()
    return u


@auth.post("/login", response_model=TokenOut)
async def login_ep(data: LoginIn, db=Depends(get_db)):
    return await login(db, data)


@auth.post("/forgot-password")
async def forgot_password(data: ForgotPasswordIn, request: Request, db=Depends(get_db)):
    # Always return the same response so the endpoint does not reveal whether an email exists.
    generic = {"message": "If an account exists for that email, a password reset link has been sent."}
    user = await db.scalar(select(User).where(User.email == data.email.lower()))
    if not user:
        return generic
    now = datetime.now(timezone.utc)
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=now + timedelta(minutes=get_settings().password_reset_expire_minutes),
    )
    db.add(reset)
    await db.commit()
    origin = request.headers.get("origin") or get_settings().frontend_url
    link = f"{origin.rstrip('/')}/reset-password?token={raw}"
    body = (
        f"Hello {user.name},\n\n"
        f"Use this link to reset your QueueLess password:\n{link}\n\n"
        f"This link expires in {get_settings().password_reset_expire_minutes} minutes "
        "and can only be used once.\n\n"
        "If you did not request this, you can ignore this email."
    )
    try:
        delivered = await send_email(user.email, "QueueLess password reset", body)
        if not delivered:
            log.warning("password_reset_link", extra={"email": user.email, "reset_link": link})
    except Exception:
        log.exception("password_reset_email_failed")
    return generic


@auth.post("/reset-password")
async def reset_password(data: ResetPasswordIn, db=Depends(get_db)):
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    reset = await db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )
    if not reset or reset.used_at is not None or reset.expires_at <= now:
        raise HTTPException(400, "This password reset link is invalid or expired")
    user = await db.get(User, reset.user_id)
    if not user:
        raise HTTPException(400, "This password reset link is invalid or expired")
    user.password_hash = hash_password(data.password)
    reset.used_at = now
    await db.commit()
    return {"message": "Password reset successfully. You can now sign in with your new password."}


@auth.post("/register-organization", response_model=UserOut)
async def register_organization(data: OrganizationRegisterIn, db=Depends(get_db)):
    email = data.email.lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    org = Organization(
        name=data.organization_name,
        description=data.description,
        address=data.address,
        timezone=data.timezone,
    )
    db.add(org)
    await db.flush()
    user = User(
        name=data.name,
        email=email,
        password_hash=hash_password(data.password),
        role=Role.ORG_ADMIN,
        org_id=org.id,
    )
    db.add(user)
    await db.flush()
    await audit(db, org.id, user.id, "CREATE", "Organization", org.id)
    await db.commit()
    _cache_delete(_ORG_LIST_KEY)
    return user


@auth.post("/refresh", response_model=TokenOut)
async def refresh_ep(data: dict, db=Depends(get_db)):
    try:
        p = decode_token(data["refresh_token"])
        assert p["type"] == "refresh"
        u = await db.get(User, p["sub"])
    except Exception:
        raise HTTPException(401, "Invalid refresh token")
    return {
        "access_token": create_access_token(u.id, u.role.value),
        "refresh_token": create_refresh_token(u.id, u.role.value),
        "token_type": "bearer",
    }


@auth.post("/logout")
async def logout_ep(user=Depends(current_user)):
    return {"message": "Logged out; discard the client tokens."}


@auth.get("/me", response_model=UserOut)
async def me(user=Depends(current_user)):
    return user


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

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
    if not o or (user.org_id and user.org_id != o.id):
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
    if not o or (user.org_id and user.org_id != o.id):
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
    if user.org_id != org_id:
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
    if user.org_id != org_id:
        raise HTTPException(403, "Organization access denied")
    staff = await db.get(User, staff_id)
    if not staff or staff.org_id != org_id or staff.role != Role.STAFF:
        raise HTTPException(404, "Staff member not found")
    await db.execute(delete(StaffService).where(StaffService.staff_id == staff.id))
    staff.org_id = None
    await audit(db, org_id, user.id, "REMOVE", "User", staff.id)
    await db.commit()
    return {"message": "Staff member removed from organization"}


# ---------------------------------------------------------------------------
# Services (direct)
# ---------------------------------------------------------------------------

@router.patch("/services/{service_id}", response_model=ServiceOut)
async def patch_service(
    service_id,
    data: ServiceCreate,
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN)),
):
    s = await db.get(Service, service_id)
    if not s or (user.org_id and user.org_id != s.organization_id):
        raise HTTPException(404, "Service not found")
    for k, v in data.model_dump().items():
        setattr(s, k, v)
    await audit(db, s.organization_id, user.id, "UPDATE", "Service", s.id)
    await db.commit()
    _cache_delete(_ORG_SVC_KEY.format(org_id=str(s.organization_id)))
    return s


@router.delete("/services/{service_id}")
async def delete_service(
    service_id,
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN)),
):
    s = await db.get(Service, service_id)
    if not s or (user.org_id and user.org_id != s.organization_id):
        raise HTTPException(404, "Service not found")
    s.status = Status.INACTIVE
    await db.commit()
    _cache_delete(
        _ORG_LIST_KEY,
        _ORG_SVC_KEY.format(org_id=str(s.organization_id)),
    )
    return {"message": "Service deactivated"}


# ---------------------------------------------------------------------------
# Queues
# ---------------------------------------------------------------------------

@queues.get("/services/{service_id}/queue", response_model=QueueOut)
async def get_queue(service_id, db=Depends(get_db)):
    service = await db.get(Service, service_id)
    if not service or service.status != Status.ACTIVE:
        raise HTTPException(404, "Service not found")
    org = await db.get(Organization, service.organization_id)
    try:
        local_date = datetime.now(ZoneInfo(org.timezone if org else "UTC")).date()
    except Exception:
        local_date = datetime.now(timezone.utc).date()
    q = await db.scalar(
        select(Queue).where(Queue.service_id == service_id, Queue.queue_date == local_date)
    )
    if not q:
        q = Queue(service_id=service_id, queue_date=local_date)
        db.add(q)
        await db.commit()
        await db.refresh(q)
    _, waiting = await queue_snapshot(db, q.id)
    return QueueOut(
        id=q.id,
        service_id=q.service_id,
        queue_date=q.queue_date,
        status=q.status,
        current_token=q.current_token,
        people_waiting=waiting,
        last_token_number=q.last_token_number,
    )


@queues.post("/services/{service_id}/queue/join", response_model=JoinOut)
async def join(service_id, db=Depends(get_db), user=Depends(current_user)):
    token, pos = await join_queue(db, service_id, user)
    await db.commit()
    await publish_queue_state(db, token.queue_id)
    return JoinOut(
        id=token.id,
        queue_id=token.queue_id,
        token_code=token.token_code,
        position=pos,
        estimated_wait=token.estimated_wait,
        status=token.status,
        wait_minutes=0,
        service_minutes=None,
    )


@queues.post("/queues/{queue_id}/leave")
async def leave(queue_id, db=Depends(get_db), user=Depends(current_user)):
    t = await db.scalar(
        select(QueueToken).where(
            QueueToken.queue_id == queue_id,
            QueueToken.user_id == user.id,
            QueueToken.status.in_([TokenStatus.WAITING, TokenStatus.CALLED]),
        )
    )
    if not t:
        raise HTTPException(404, "Active token not found")
    t.status = TokenStatus.CANCELLED
    await db.commit()
    await publish_queue_state(db, queue_id)
    return {"message": "Token cancelled"}


@queues.get("/queues/{queue_id}/position", response_model=JoinOut)
async def position(queue_id, db=Depends(get_db), user=Depends(current_user)):
    t = await db.scalar(
        select(QueueToken).where(
            QueueToken.queue_id == queue_id,
            QueueToken.user_id == user.id,
            QueueToken.status.in_([TokenStatus.WAITING, TokenStatus.CALLED, TokenStatus.SERVING]),
        ).order_by(QueueToken.joined_at.desc())
    )
    if not t:
        raise HTTPException(404, "Active token not found")
    ahead = (
        await db.scalar(
            select(func.count()).select_from(QueueToken).where(
                QueueToken.queue_id == queue_id,
                QueueToken.status == TokenStatus.WAITING,
                QueueToken.joined_at < t.joined_at,
            )
        )
    ) or 0
    now = datetime.now(timezone.utc)
    wait_minutes = (
        round(((t.service_started_at or now) - t.joined_at).total_seconds() / 60)
        if t.joined_at
        else None
    )
    service_minutes = (
        round(((t.completed_at or now) - t.service_started_at).total_seconds() / 60)
        if t.service_started_at
        else None
    )
    return JoinOut(
        id=t.id,
        queue_id=t.queue_id,
        token_code=t.token_code,
        position=ahead + 1,
        estimated_wait=t.estimated_wait,
        status=t.status,
        wait_minutes=max(0, wait_minutes) if wait_minutes is not None else None,
        service_minutes=max(0, service_minutes) if service_minutes is not None else None,
    )


async def staff_token(token_id, action, db, user):
    t = await db.get(QueueToken, token_id)
    if not t:
        raise HTTPException(404, "Token not found")
    s = await db.scalar(
        select(Service).join(Queue).where(Queue.id == t.queue_id, Service.id == Queue.service_id)
    )
    if user.role != Role.ORG_ADMIN:
        assigned = await db.scalar(
            select(StaffService).where(
                StaffService.staff_id == user.id,
                StaffService.service_id == s.id,
            )
        )
        if not assigned:
            raise HTTPException(403, "Service not assigned")
    new = {
        "start": TokenStatus.SERVING,
        "complete": TokenStatus.COMPLETED,
        "skip": TokenStatus.SKIPPED,
        "recall": TokenStatus.CALLED,
    }[action]
    t = await transition(db, token_id, new)
    await db.commit()
    await publish_queue_state(db, t.queue_id)
    return t


@queues.post("/queues/{queue_id}/call-next", response_model=TokenOutDetail)
async def call(
    queue_id,
    db=Depends(get_db),
    user=Depends(require_roles(Role.STAFF, Role.ORG_ADMIN)),
):
    q = await db.get(Queue, queue_id)
    s = await db.get(Service, q.service_id) if q else None
    if not q or not s:
        raise HTTPException(404, "Queue not found")
    if user.role == Role.STAFF and not await db.scalar(
        select(StaffService).where(
            StaffService.staff_id == user.id,
            StaffService.service_id == s.id,
        )
    ):
        raise HTTPException(403, "Service not assigned")
    t = await call_next(db, queue_id)
    await db.commit()
    await publish_queue_state(db, queue_id)
    return t


@queues.post("/tokens/{token_id}/start", response_model=TokenOutDetail)
async def start(
    token_id,
    db=Depends(get_db),
    user=Depends(require_roles(Role.STAFF, Role.ORG_ADMIN)),
):
    return await staff_token(token_id, "start", db, user)


@queues.post("/tokens/{token_id}/complete", response_model=TokenOutDetail)
async def complete(
    token_id,
    db=Depends(get_db),
    user=Depends(require_roles(Role.STAFF, Role.ORG_ADMIN)),
):
    return await staff_token(token_id, "complete", db, user)


@queues.post("/tokens/{token_id}/skip", response_model=TokenOutDetail)
async def skip(
    token_id,
    db=Depends(get_db),
    user=Depends(require_roles(Role.STAFF, Role.ORG_ADMIN)),
):
    return await staff_token(token_id, "skip", db, user)


@queues.post("/tokens/{token_id}/recall", response_model=TokenOutDetail)
async def recall(
    token_id,
    db=Depends(get_db),
    user=Depends(require_roles(Role.STAFF, Role.ORG_ADMIN)),
):
    return await staff_token(token_id, "recall", db, user)


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

@appointments.get("", response_model=list[AppointmentOut])
async def list_appointments(db=Depends(get_db), user=Depends(current_user)):
    rows = (
        await db.scalars(
            select(Appointment)
            .where(Appointment.user_id == user.id)
            .order_by(Appointment.appointment_date)
        )
    ).all()
    out = []
    for a in rows:
        svc = await db.get(Service, a.service_id)
        out.append(
            AppointmentOut(
                id=a.id,
                service_id=a.service_id,
                user_id=a.user_id,
                appointment_date=a.appointment_date,
                start_time=a.start_time,
                end_time=a.end_time,
                status=a.status,
                service_name=svc.name if svc else None,
            )
        )
    return out


@appointments.post("", response_model=AppointmentOut)
async def book(
    data: AppointmentCreate,
    db=Depends(get_db),
    user=Depends(current_user),
):
    a = await create_appointment(db, data, user.id)
    await db.commit()
    note = await db.scalar(
        select(Notification)
        .where(Notification.user_id == user.id, Notification.type == "APPOINTMENT_BOOKED")
        .order_by(Notification.created_at.desc())
    )
    if note:
        try:
            send_notification_email.delay(str(note.id))
        except Exception:
            pass
    svc = await db.get(Service, a.service_id)
    return AppointmentOut(
        id=a.id,
        service_id=a.service_id,
        user_id=a.user_id,
        appointment_date=a.appointment_date,
        start_time=a.start_time,
        end_time=a.end_time,
        status=a.status,
        service_name=svc.name if svc else None,
    )


@appointments.get("/{appointment_id}", response_model=AppointmentOut)
async def get_appt(appointment_id, db=Depends(get_db), user=Depends(current_user)):
    a = await db.get(Appointment, appointment_id)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Appointment not found")
    return a


@appointments.post("/{appointment_id}/cancel")
async def cancel(appointment_id, db=Depends(get_db), user=Depends(current_user)):
    a = await db.get(Appointment, appointment_id)
    if not a or a.user_id != user.id:
        raise HTTPException(404, "Appointment not found")
    a.status = AppointmentStatus.CANCELLED
    await db.commit()
    return a


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@analytics.get("/overview", response_model=AnalyticsOut)
async def overview(
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN, Role.STAFF)),
):
    base = (
        select(QueueToken).join(Queue).join(Service).where(Service.organization_id == user.org_id)
        if user.org_id
        else select(QueueToken)
    )
    toks = (await db.scalars(base)).all()
    completed = [
        t for t in toks
        if t.status == TokenStatus.COMPLETED and t.joined_at and t.completed_at
    ]
    waits = [
        (t.service_started_at - t.joined_at).total_seconds() / 60
        for t in completed
        if t.service_started_at
    ]
    services = [
        (t.completed_at - t.service_started_at).total_seconds() / 60
        for t in completed
        if t.service_started_at and t.completed_at
    ]
    cancelled = (
        await db.scalar(
            select(func.count()).select_from(Appointment).where(
                Appointment.status == AppointmentStatus.CANCELLED
            )
        )
    ) or 0
    waiting = sum(t.status == TokenStatus.WAITING for t in toks)
    return AnalyticsOut(
        total_customers=len({t.user_id for t in toks}),
        average_wait=round(sum(waits) / len(waits), 2) if waits else 0,
        average_service_time=round(sum(services) / len(services), 2) if services else 0,
        completed_tokens=len(completed),
        skipped_tokens=sum(t.status == TokenStatus.SKIPPED for t in toks),
        cancelled_appointments=cancelled,
        peak_hour=None,
        queue_length=waiting,
    )


@analytics.get("/queues")
async def queue_stats(
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN, Role.STAFF)),
):
    rows = []
    queues_list = (await db.scalars(select(Queue).order_by(Queue.created_at))).all()
    for q in queues_list:
        service = await db.get(Service, q.service_id)
        if not service or (user.org_id and service.organization_id != user.org_id):
            continue
        if user.role == Role.STAFF and not await db.scalar(
            select(StaffService).where(
                StaffService.staff_id == user.id,
                StaffService.service_id == service.id,
            )
        ):
            continue
        waiting = (
            await db.scalar(
                select(func.count()).select_from(QueueToken).where(
                    QueueToken.queue_id == q.id,
                    QueueToken.status == TokenStatus.WAITING,
                )
            )
        ) or 0
        rows.append({
            "queue_id": str(q.id),
            "service_id": str(q.service_id),
            "service_name": service.name,
            "current_token": q.current_token,
            "waiting": waiting,
        })
    return rows


@analytics.get("/wait-times")
async def wait_times(
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN, Role.STAFF)),
):
    return {"average_wait_minutes": (await overview(db, user)).average_wait}


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@router.get("/notifications", response_model=list[NotificationOut])
async def notifications(db=Depends(get_db), user=Depends(current_user)):
    return (
        await db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
    ).all()


@router.post("/notifications/{notification_id}/read")
async def mark_read(notification_id, db=Depends(get_db), user=Depends(current_user)):
    n = await db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    n.status = NotificationStatus.READ
    n.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "read"}


# ---------------------------------------------------------------------------
# Include sub-routers
# ---------------------------------------------------------------------------
router.include_router(auth)
router.include_router(orgs)
router.include_router(queues)
router.include_router(appointments)
router.include_router(analytics)
