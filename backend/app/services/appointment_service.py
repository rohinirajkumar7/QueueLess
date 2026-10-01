from sqlalchemy import select
from fastapi import HTTPException
from datetime import datetime, timezone
from app.models.models import Appointment, AppointmentStatus, Service, Status
from app.services.notification_service import create_notification

async def create_appointment(db,data,user_id):
    if data.start_time>=data.end_time:
        raise HTTPException(422,"End time must be after start time")
    if data.appointment_date < datetime.now(timezone.utc).date():
        raise HTTPException(422,"Appointment date must be today or a future date")
    service=await db.scalar(select(Service).where(Service.id==data.service_id,Service.status==Status.ACTIVE).with_for_update())
    if not service:
        raise HTTPException(404,"Service not found or inactive")
    overlap=await db.scalar(select(Appointment).where(
        Appointment.service_id==data.service_id,
        Appointment.appointment_date==data.appointment_date,
        Appointment.status.in_([AppointmentStatus.BOOKED,AppointmentStatus.CONFIRMED,AppointmentStatus.CHECKED_IN]),
        Appointment.start_time<data.end_time,
        Appointment.end_time>data.start_time
    ).with_for_update())
    if overlap:
        raise HTTPException(409,"Appointment conflicts with an existing booking")
    a=Appointment(**data.model_dump(),user_id=user_id)
    db.add(a); await db.flush()
    msg=(f"Your appointment for {service.name} is booked for {data.appointment_date} "
         f"from {data.start_time.strftime('%H:%M')} to {data.end_time.strftime('%H:%M')}. "
         "Please arrive a few minutes early.")
    await create_notification(db,user_id,"APPOINTMENT_BOOKED","Appointment booked",msg)
    return a
