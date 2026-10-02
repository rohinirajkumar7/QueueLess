import asyncio
import time
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.responses import Response
from sqlalchemy import text

from app.api.v1.router import router
from app.core.database import engine
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.logging import configure_logging, request_logging_middleware
from app.websocket.manager import manager, redis_subscriber_loop

settings = get_settings()
configure_logging(settings.log_level)

log = logging.getLogger("queueless.main")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="QueueLess API",
    version="1.0.0",
    description="Real-time queue and appointment management",
)

# Attach limiter to app state (required by slowapi)
app.state.limiter = limiter

# Register 429 handler — returns clean JSON instead of an unhandled exception
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_logging_middleware)

REQ = Counter("queueless_http_requests_total", "HTTP requests", ["method", "path", "status"])
DUR = Histogram("queueless_http_request_duration_seconds", "Request duration", ["path"])
WS = Gauge("queueless_websocket_connections", "Active WebSocket connections")

app.include_router(router)


# ---------------------------------------------------------------------------
# Startup / shutdown: start the Redis pub/sub subscriber once per worker
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    app.state.ws_subscriber_task = asyncio.create_task(
        redis_subscriber_loop(settings.redis_url)
    )
    log.info("WS Redis subscriber task started")


@app.on_event("shutdown")
async def shutdown_event():
    task = getattr(app.state, "ws_subscriber_task", None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    log.info("WS Redis subscriber task stopped")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    try:
        async with engine.connect() as c:
            await c.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        return Response(
            content='{"status":"not_ready"}',
            status_code=503,
            media_type="application/json",
        )


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.websocket("/ws/queues/{queue_id}")
async def queue_ws(websocket: WebSocket, queue_id: str):
    await manager.connect(queue_id, websocket)
    WS.inc()
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(queue_id, websocket)
        WS.dec()


@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    REQ.labels(request.method, request.url.path, response.status_code).inc()
    DUR.labels(request.url.path).observe(time.perf_counter() - start)
    return response
