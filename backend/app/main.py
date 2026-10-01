import time, logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from sqlalchemy import text
from app.api.v1.router import router
from app.core.database import engine
from app.core.config import get_settings
from app.core.logging import configure_logging, request_logging_middleware
from app.websocket.manager import manager

settings=get_settings(); configure_logging(settings.log_level)
app=FastAPI(title="QueueLess API",version="1.0.0",description="Real-time queue and appointment management")
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_list,allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.middleware("http")(request_logging_middleware)
REQ=Counter("queueless_http_requests_total","HTTP requests",["method","path","status"]); DUR=Histogram("queueless_http_request_duration_seconds","Request duration",["path"]); WS=Gauge("queueless_websocket_connections","Active WebSocket connections")
app.include_router(router)
@app.get("/health")
async def health(): return {"status":"ok"}
@app.get("/ready")
async def ready():
    try:
        async with engine.connect() as c: await c.execute(text("SELECT 1"))
        return {"status":"ready"}
    except Exception: return Response(content='{"status":"not_ready"}',status_code=503,media_type="application/json")
@app.get("/metrics")
async def metrics(): return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)
@app.websocket("/ws/queues/{queue_id}")
async def queue_ws(websocket:WebSocket,queue_id:str):
    await manager.connect(queue_id,websocket); WS.inc()
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: pass
    finally: await manager.disconnect(queue_id,websocket); WS.dec()
@app.middleware("http")
async def metrics_middleware(request,call_next):
    start=time.perf_counter(); response=await call_next(request); REQ.labels(request.method,request.url.path,response.status_code).inc(); DUR.labels(request.url.path).observe(time.perf_counter()-start); return response
