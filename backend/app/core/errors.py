from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.logging import request_id_ctx

def error_response(code, message, status=400, details=None):
    return JSONResponse(status_code=status, content={"error":{"code":code,"message":message,"details":details or {}},"request_id":request_id_ctx.get()})
