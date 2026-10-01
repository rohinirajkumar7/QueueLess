import json, logging, time, uuid
from contextvars import ContextVar
from fastapi import Request
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_STANDARD_ATTRS = set(logging.LogRecord(
    "", 0, "", 0, "", (), None
).__dict__.keys()) | {"message", "asctime"}

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"), "level": record.levelname, "message": record.getMessage(), "request_id": request_id_ctx.get()}
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)

def configure_logging(level="INFO"):
    handler = logging.StreamHandler(); handler.setFormatter(JsonFormatter())
    root = logging.getLogger(); root.handlers.clear(); root.addHandler(handler); root.setLevel(level)

async def request_logging_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4())); request_id_ctx.set(rid); start=time.perf_counter()
    response = await call_next(request); response.headers["X-Request-ID"] = rid
    logging.getLogger("queueless").info("request", extra={"endpoint": request.url.path, "status": response.status_code, "duration_ms": round((time.perf_counter()-start)*1000,2)})
    return response