from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.models.models import User, Role
bearer=HTTPBearer(auto_error=False)
async def current_user(creds:HTTPAuthorizationCredentials=Depends(bearer),db:AsyncSession=Depends(get_db)):
    if not creds: raise HTTPException(401,"Authentication required")
    try:
        p=decode_token(creds.credentials)
        if p.get("type")!="access": raise ValueError()
        uid=UUID(p["sub"])
    except Exception: raise HTTPException(401,"Invalid or expired token")
    user=await db.get(User,uid)
    if not user: raise HTTPException(401,"User not found")
    return user
def require_roles(*roles):
    async def checker(user=Depends(current_user)):
        if user.role not in roles: raise HTTPException(403,"Insufficient permissions")
        return user
    return checker
