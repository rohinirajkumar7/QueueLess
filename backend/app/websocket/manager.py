import asyncio
import json
import logging
from collections import defaultdict
from fastapi import WebSocket
from redis import asyncio as redis_asyncio

log = logging.getLogger("queueless.websocket.manager")


class ConnectionManager:
    def __init__(self):
        self.rooms = defaultdict(set)
        self.lock = asyncio.Lock()

    async def connect(self, queue_id, ws):
        await ws.accept()
        async with self.lock:
            self.rooms[str(queue_id)].add(ws)

    async def disconnect(self, queue_id, ws):
        async with self.lock:
            self.rooms[str(queue_id)].discard(ws)

    async def broadcast(self, queue_id, message):
        dead = []
        for ws in list(self.rooms[str(queue_id)]):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(queue_id, ws)


manager = ConnectionManager()


async def redis_subscriber_loop(redis_url: str):
    """Runs once per worker process for its whole lifetime. Subscribes to
    ws:queue:* and relays each message into this process's local
    manager.broadcast(). Must reconnect with backoff on failure rather
    than crash the app or exit the loop."""
    while True:
        try:
            client = redis_asyncio.from_url(redis_url, decode_responses=True)
            pubsub = client.pubsub()
            await pubsub.psubscribe("ws:queue:*")
            async for msg in pubsub.listen():
                if msg["type"] != "pmessage":
                    continue
                queue_id = msg["channel"].split(":", 2)[2]
                await manager.broadcast(queue_id, json.loads(msg["data"]))
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("WS redis subscriber lost connection, retrying in 2s", exc_info=True)
            await asyncio.sleep(2)
