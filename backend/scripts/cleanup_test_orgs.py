#!/usr/bin/env python3
"""
scripts/cleanup_test_orgs.py
-----------------------------
Delete test organizations that should never appear in the customer listing.

This script removes:
  1. Organizations where is_test=True  (the correct programmatic flag)
  2. Organizations whose name matches the legacy pattern
     "Concurrency Test Org ..." (created before the is_test column existed)

It ONLY deletes rows it is certain are test data.  Real (is_test=False)
organizations with non-matching names are never touched.

Usage:
    # Inside the backend container:
    python scripts/cleanup_test_orgs.py

    # Or against an arbitrary DATABASE_URL:
    DATABASE_URL=postgresql+asyncpg://... python scripts/cleanup_test_orgs.py

    # Dry-run (print what would be deleted, no changes):
    python scripts/cleanup_test_orgs.py --dry-run
"""
import asyncio
import os
import sys
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import get_settings
from app.models.models import (
    Organization, Service, Queue, QueueToken, StaffService,
    User, Notification, Appointment, AuditLog,
)

LEGACY_NAME_PREFIX = "Concurrency Test Org"


async def main(dry_run: bool) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

    async with Session() as db:
        # Find all test orgs (is_test=True OR legacy name pattern)
        orgs = (
            await db.scalars(
                select(Organization).where(
                    (Organization.is_test == True)
                    | Organization.name.like(f"{LEGACY_NAME_PREFIX}%")
                )
            )
        ).all()

        if not orgs:
            print("No test organizations found — nothing to delete.")
            return

        print(f"Found {len(orgs)} test organization(s):")
        for o in orgs:
            flag = "[is_test]" if o.is_test else "[legacy name]"
            print(f"  {flag}  {o.id}  {o.name!r}")

        if dry_run:
            print("\n[DRY-RUN] No changes made.")
            return

        org_ids = [o.id for o in orgs]

        # Delete in dependency order
        # 1. Queue tokens → queues (for services of these orgs)
        service_ids_rows = (
            await db.scalars(
                select(Service.id).where(Service.organization_id.in_(org_ids))
            )
        ).all()
        service_ids = list(service_ids_rows)

        if service_ids:
            queue_ids_rows = (
                await db.scalars(
                    select(Queue.id).where(Queue.service_id.in_(service_ids))
                )
            ).all()
            queue_ids = list(queue_ids_rows)

            if queue_ids:
                r = await db.execute(
                    delete(QueueToken).where(QueueToken.queue_id.in_(queue_ids))
                )
                print(f"  Deleted {r.rowcount} queue token(s)")

            r = await db.execute(
                delete(Queue).where(Queue.service_id.in_(service_ids))
            )
            print(f"  Deleted {r.rowcount} queue(s)")

            r = await db.execute(
                delete(StaffService).where(StaffService.service_id.in_(service_ids))
            )
            print(f"  Deleted {r.rowcount} staff-service assignment(s)")

            r = await db.execute(
                delete(Appointment).where(Appointment.service_id.in_(service_ids))
            )
            print(f"  Deleted {r.rowcount} appointment(s)")

            r = await db.execute(
                delete(Service).where(Service.id.in_(service_ids))
            )
            print(f"  Deleted {r.rowcount} service(s)")

        # 2. Audit logs referencing these orgs
        r = await db.execute(
            delete(AuditLog).where(AuditLog.organization_id.in_(org_ids))
        )
        print(f"  Deleted {r.rowcount} audit log(s)")

        # 3. Users belonging to these orgs (set org_id=NULL for non-admin users
        #    created during tests; hard-delete test users with test email patterns)
        test_users = (
            await db.scalars(
                select(User).where(
                    User.org_id.in_(org_ids)
                    | User.email.like("conc-%@test.local")
                    | User.email.like("k6-%@k6loadtest.io")
                )
            )
        ).all()
        test_user_ids = [u.id for u in test_users]

        if test_user_ids:
            # Delete their notifications first
            r = await db.execute(
                delete(Notification).where(
                    Notification.user_id.in_(test_user_ids)
                )
            )
            print(f"  Deleted {r.rowcount} notification(s) for test users")

            r = await db.execute(
                delete(User).where(User.id.in_(test_user_ids))
            )
            print(f"  Deleted {r.rowcount} test user(s)")

        # 4. Organizations
        r = await db.execute(
            delete(Organization).where(Organization.id.in_(org_ids))
        )
        print(f"  Deleted {r.rowcount} organization(s)")

        await db.commit()
        print("\nCleanup complete.")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete test organizations from QueueLess DB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without making any changes",
    )
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
