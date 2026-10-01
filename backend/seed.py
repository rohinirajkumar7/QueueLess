import asyncio
from datetime import date, time, datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.models import (
    Organization, Service, StaffService, Queue, QueueToken,
    Appointment, User, Role, Status,
)


async def get_or_create_user(db, email, name, password, role, org_id=None):
    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=role,
            org_id=org_id,
        )
        db.add(user)
        await db.flush()
    return user


async def main():
    async with SessionLocal() as db:
        # Demo organization — is_test=False so it appears in the customer listing.
        org = await db.scalar(
            select(Organization).where(Organization.name == "QueueLess Demo Clinic")
        )
        if not org:
            org = Organization(
                name="QueueLess Demo Clinic",
                description="Development-only demo organization",
                address="123 Demo Street",
                timezone="UTC",
                is_test=False,  # explicitly not a test org
            )
            db.add(org)
            await db.flush()
        else:
            # Ensure existing demo org is not accidentally flagged as test.
            org.is_test = False

        admin = await get_or_create_user(
            db, "admin@queueless.example.com", "Demo Admin", "Admin123!", Role.ORG_ADMIN, org.id
        )
        staff = await get_or_create_user(
            db, "staff@queueless.example.com", "Demo Staff", "Staff123!", Role.STAFF, org.id
        )
        customer = await get_or_create_user(
            db, "customer@queueless.example.com", "Demo Customer", "Customer123!", Role.CUSTOMER
        )

        s1 = await db.scalar(
            select(Service).where(Service.organization_id == org.id, Service.code == "GEN")
        )
        if not s1:
            s1 = Service(
                organization_id=org.id,
                name="General Consultation",
                code="GEN",
                description="General services",
                average_service_time=10,
                queue_capacity=100,
            )
            db.add(s1)
            await db.flush()

        s2 = await db.scalar(
            select(Service).where(Service.organization_id == org.id, Service.code == "BIL")
        )
        if not s2:
            s2 = Service(
                organization_id=org.id,
                name="Billing",
                code="BIL",
                description="Billing support",
                average_service_time=8,
                queue_capacity=50,
            )
            db.add(s2)
            await db.flush()

        assignment = await db.scalar(
            select(StaffService).where(
                StaffService.staff_id == staff.id,
                StaffService.service_id == s1.id,
            )
        )
        if not assignment:
            db.add(StaffService(staff_id=staff.id, service_id=s1.id))

        today = datetime.now(ZoneInfo(org.timezone)).date()
        q = await db.scalar(
            select(Queue).where(Queue.service_id == s1.id, Queue.queue_date == today)
        )
        if not q:
            q = Queue(service_id=s1.id, queue_date=today, last_token_number=0)
            db.add(q)
            await db.flush()

        token = await db.scalar(
            select(QueueToken).where(
                QueueToken.queue_id == q.id, QueueToken.user_id == customer.id
            )
        )
        if not token:
            q.last_token_number = max(q.last_token_number or 0, 1)
            db.add(
                QueueToken(
                    queue_id=q.id,
                    user_id=customer.id,
                    token_number=1,
                    token_code="GEN-001",
                    estimated_wait=0,
                )
            )

        appointment = await db.scalar(
            select(Appointment).where(
                Appointment.service_id == s1.id,
                Appointment.user_id == customer.id,
                Appointment.appointment_date == today,
            )
        )
        if not appointment:
            db.add(
                Appointment(
                    service_id=s1.id,
                    user_id=customer.id,
                    appointment_date=today,
                    start_time=time(14, 0),
                    end_time=time(14, 15),
                )
            )

        await db.commit()
        print("QueueLess development seed is ready.")
        print(
            "Demo accounts: "
            "admin@queueless.example.com / Admin123!, "
            "staff@queueless.example.com / Staff123!, "
            "customer@queueless.example.com / Customer123!"
        )


asyncio.run(main())
