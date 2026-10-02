"""
Appointments routes: list_appointments, book, get_appt, cancel.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import current_user
from app.core.database import get_db
from app.models.models import Appointment, AppointmentStatus, Notification, Service
from app.schemas.schemas import AppointmentCreate, AppointmentOut
from app.services.appointment_service import create_appointment
from app.workers.tasks import send_notification_email

appointments = APIRouter(prefix="/appointments", tags=["appointments"])


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
