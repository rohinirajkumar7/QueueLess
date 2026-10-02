"""
Analytics routes: overview, queue_stats, wait_times.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func

from app.api.deps import require_roles
from app.core.database import get_db
from app.models.models import (
    Appointment, AppointmentStatus, Queue, QueueToken, Role, Service,
    StaffService, Status, TokenStatus,
)
from app.schemas.schemas import AnalyticsOut

analytics = APIRouter(prefix="/analytics", tags=["analytics"])


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
    # Fetch active services belonging to this organization
    services_stmt = select(Service).where(
        Service.status == Status.ACTIVE,
        Service.organization_id == user.org_id,
    )
    if user.role == Role.STAFF:
        services_stmt = services_stmt.join(
            StaffService, StaffService.service_id == Service.id
        ).where(StaffService.staff_id == user.id)

    services_list = (await db.scalars(services_stmt)).all()

    for service in services_list:
        # Get the latest active queue for this service
        latest_queue = await db.scalar(
            select(Queue)
            .where(Queue.service_id == service.id, Queue.status == Status.ACTIVE)
            .order_by(Queue.queue_date.desc(), Queue.created_at.desc())
            .limit(1)
        )
        if not latest_queue:
            continue

        waiting = (
            await db.scalar(
                select(func.count()).select_from(QueueToken).where(
                    QueueToken.queue_id == latest_queue.id,
                    QueueToken.status == TokenStatus.WAITING,
                )
            )
        ) or 0
        rows.append({
            "queue_id": str(latest_queue.id),
            "service_id": str(service.id),
            "service_name": service.name,
            "current_token": latest_queue.current_token,
            "waiting": waiting,
        })
    return rows


@analytics.get("/wait-times")
async def wait_times(
    db=Depends(get_db),
    user=Depends(require_roles(Role.ORG_ADMIN, Role.STAFF)),
):
    return {"average_wait_minutes": (await overview(db, user)).average_wait}
