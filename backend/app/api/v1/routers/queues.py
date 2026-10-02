"""
Queues routes: get_queue, join, leave, position, call_next, start, complete, skip, recall.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func

from app.api.deps import current_user, require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.models.models import (
    Organization, Queue, QueueToken, Role, Service, StaffService, Status, TokenStatus,
)
from app.schemas.schemas import JoinOut, QueueOut, TokenOutDetail
from app.services.queue_service import call_next, join_queue, queue_snapshot, transition
from app.websocket.events import publish_queue_state

_settings = get_settings()

queues = APIRouter(prefix="", tags=["queues"])


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
@limiter.limit(_settings.rate_limit_queue_join)
async def join(request: Request, service_id, db=Depends(get_db), user=Depends(current_user)):
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
