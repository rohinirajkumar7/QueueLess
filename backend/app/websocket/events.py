from sqlalchemy import select, func
from app.models.models import Queue, QueueToken, TokenStatus
from app.websocket.manager import manager


async def publish_queue_state(db, queue_id):
    # If no clients are connected to this room, skip redundant DB queries
    if not manager.rooms.get(str(queue_id)):
        return

    q = await db.get(Queue, queue_id)
    if not q:
        return
    waiting = (
        await db.scalar(
            select(func.count()).select_from(QueueToken).where(
                QueueToken.queue_id == queue_id,
                QueueToken.status == TokenStatus.WAITING,
            )
        )
    ) or 0
    await manager.broadcast(
        str(queue_id),
        {
            "event": "QUEUE_UPDATED",
            "queue_id": str(queue_id),
            "current_token": q.current_token,
            "people_waiting": waiting,
        },
    )
