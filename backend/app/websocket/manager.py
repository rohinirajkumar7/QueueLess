from collections import defaultdict
from fastapi import WebSocket
import asyncio
class ConnectionManager:
    def __init__(self):
        self.rooms=defaultdict(set)
        self.lock=asyncio.Lock()
    async def connect(self,queue_id,ws):
        await ws.accept()
        async with self.lock:
            self.rooms[str(queue_id)].add(ws)
    async def disconnect(self,queue_id,ws):
        async with self.lock:
            self.rooms[str(queue_id)].discard(ws)
    async def broadcast(self,queue_id,message):
        dead=[]
        for ws in list(self.rooms[str(queue_id)]):
            try: await ws.send_json(message)
            except Exception: dead.append(ws)
        for ws in dead: await self.disconnect(queue_id,ws)
manager=ConnectionManager()
