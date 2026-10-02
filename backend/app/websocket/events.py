import json
from redis import asyncio as redis_asyncio
from sqlalchemy import select, func
from app.core.config import get_settings
from app.models.models import Queue, QueueToken, TokenStatus

_settings = get_settings()
try:
    _redis = redis_asyncio.from_url(_settings.redis_url, decode_responses=True)
except Exception:
    _redis = None


async def publish_queue_state(db, queue_id):
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
    payload = {
        "event": "QUEUE_UPDATED",
        "queue_id": str(queue_id),
        "current_token": q.current_token,
        "people_waiting": waiting,
    }
    try:
        if _redis:
            await _redis.publish(f"ws:queue:{queue_id}", json.dumps(payload))
    except Exception:
        pass  # degrade gracefully — same pattern already used for the sync cache client in router.py
