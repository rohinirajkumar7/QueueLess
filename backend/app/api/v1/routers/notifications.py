"""
Notifications routes: get notifications, mark_read.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import current_user
from app.core.database import get_db
from app.models.models import Notification, NotificationStatus
from app.schemas.schemas import NotificationOut

router = APIRouter()


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


# Alias for backward compatibility
notifications = router
