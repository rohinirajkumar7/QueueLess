"""
Unit tests for Task 6: Cross-worker WebSocket fan-out via Redis Pub/Sub.

Verifies:
(a) publish_queue_state() calls redis.publish with channel ws:queue:{queue_id}
    and the correct JSON payload shape (event, queue_id, current_token, people_waiting).
(b) redis_subscriber_loop receives a pub/sub pmessage and relays it into
    local manager.broadcast() with the right queue_id and payload.
"""
import asyncio
import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.models import Queue
from app.websocket import events
from app.websocket import manager


@pytest.mark.asyncio
async def test_publish_queue_state_publishes_to_redis():
    """
    publish_queue_state must query the DB for the queue state and publish
    a JSON payload to the Redis channel 'ws:queue:{queue_id}'.
    """
    queue_id = uuid.uuid4()
    mock_queue = MagicMock()
    mock_queue.current_token = "A-005"

    mock_db = AsyncMock()
    # db.get(Queue, queue_id) -> mock_queue
    mock_db.get.return_value = mock_queue
    # db.scalar(...) for count -> 3 waiting
    mock_db.scalar.return_value = 3

    mock_redis = AsyncMock()

    with patch.object(events, "_redis", mock_redis):
        await events.publish_queue_state(mock_db, queue_id)

    # Verify publish was called
    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args[0]
    channel, raw_payload = call_args

    assert channel == f"ws:queue:{queue_id}", f"Unexpected channel: {channel}"

    payload = json.loads(raw_payload)
    assert payload == {
        "event": "QUEUE_UPDATED",
        "queue_id": str(queue_id),
        "current_token": "A-005",
        "people_waiting": 3,
    }


@pytest.mark.asyncio
async def test_redis_subscriber_loop_relays_to_manager_broadcast():
    """
    redis_subscriber_loop must listen to psubscribe('ws:queue:*') and relay
    received 'pmessage' entries to manager.broadcast(queue_id, payload).
    """
    queue_id = "test-queue-123"
    payload = {
        "event": "QUEUE_UPDATED",
        "queue_id": queue_id,
        "current_token": "B-001",
        "people_waiting": 2,
    }

    # Simulate an async generator of pubsub messages
    async def mock_listen():
        yield {
            "type": "pmessage",
            "pattern": "ws:queue:*",
            "channel": f"ws:queue:{queue_id}",
            "data": json.dumps(payload),
        }
        # Raise CancelledError to gracefully exit the subscriber loop in the test
        raise asyncio.CancelledError()

    mock_pubsub = MagicMock()
    mock_pubsub.psubscribe = AsyncMock()
    mock_pubsub.listen = mock_listen

    mock_client = MagicMock()
    mock_client.pubsub.return_value = mock_pubsub

    mock_broadcast = AsyncMock()

    with patch("app.websocket.manager.redis_asyncio.from_url", return_value=mock_client), \
         patch.object(manager.manager, "broadcast", mock_broadcast):
        try:
            await manager.redis_subscriber_loop("redis://mock:6379/0")
        except asyncio.CancelledError:
            pass

    # Verify psubscribe was called with pattern
    mock_pubsub.psubscribe.assert_called_once_with("ws:queue:*")

    # Verify broadcast was called with queue_id and parsed payload dict
    mock_broadcast.assert_called_once_with(queue_id, payload)
