from sqlalchemy import select
from fastapi import HTTPException
from app.models.models import User, Role
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token


async def register(db, data):
    if await db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Email already registered")
    u = User(
        name=data.name,
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        role=Role.CUSTOMER,
    )
    db.add(u)
    await db.flush()
    return u


async def login(db, data):
    u = await db.scalar(select(User).where(User.email == data.email.lower()))
    if not u or not verify_password(data.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if data.role is not None and u.role != data.role:
        raise HTTPException(403, f"This account is not a {data.role.value} account")
    return {
        "access_token": create_access_token(u.id, u.role.value),
        "refresh_token": create_refresh_token(u.id, u.role.value),
        "token_type": "bearer",
    }
