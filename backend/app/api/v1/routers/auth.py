"""
Auth routes: register, login, forgot/reset password, refresh, logout, me.
"""
import hashlib
import logging
import secrets
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete

from app.api.deps import current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)
from app.models.models import Organization, PasswordResetToken, Role, User
from app.schemas.schemas import (
    ForgotPasswordIn,
    LoginIn,
    OrganizationRegisterIn,
    RegisterIn,
    ResetPasswordIn,
    TokenOut,
    UserOut,
)
from app.services.audit_service import audit
from app.services.auth_service import register, login
from app.services.email_service import send_email
from app.api.v1.routers.shared import _cache_delete, _ORG_LIST_KEY

log = logging.getLogger("queueless.router.auth")

_settings = get_settings()

auth = APIRouter(prefix="/auth", tags=["auth"])


@auth.post("/register", response_model=UserOut)
@limiter.limit(_settings.rate_limit_login)
async def register_ep(request: Request, data: RegisterIn, db=Depends(get_db)):
    u = await register(db, data)
    await db.commit()
    return u


@auth.post("/login", response_model=TokenOut)
@limiter.limit(_settings.rate_limit_login)
async def login_ep(request: Request, data: LoginIn, db=Depends(get_db)):
    return await login(db, data)


@auth.post("/forgot-password")
@limiter.limit(_settings.rate_limit_login)
async def forgot_password(request: Request, data: ForgotPasswordIn, db=Depends(get_db)):
    # Always return the same response so the endpoint does not reveal whether an email exists.
    generic = {"message": "If an account exists for that email, a password reset link has been sent."}
    user = await db.scalar(select(User).where(User.email == data.email.lower()))
    if not user:
        return generic
    now = datetime.now(timezone.utc)
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    reset = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=now + timedelta(minutes=get_settings().password_reset_expire_minutes),
    )
    db.add(reset)
    await db.commit()
    origin = request.headers.get("origin") or get_settings().frontend_url
    link = f"{origin.rstrip('/')}/reset-password?token={raw}"
    body = (
        f"Hello {user.name},\n\n"
        f"Use this link to reset your QueueLess password:\n{link}\n\n"
        f"This link expires in {get_settings().password_reset_expire_minutes} minutes "
        "and can only be used once.\n\n"
        "If you did not request this, you can ignore this email."
    )
    try:
        delivered = await send_email(user.email, "QueueLess password reset", body)
        if not delivered:
            log.warning("password_reset_link", extra={"email": user.email, "reset_link": link})
    except Exception:
        log.exception("password_reset_email_failed")
    return generic


@auth.post("/reset-password")
async def reset_password(data: ResetPasswordIn, db=Depends(get_db)):
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    now = datetime.now(timezone.utc)
    reset = await db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .with_for_update()
    )
    if not reset or reset.used_at is not None or reset.expires_at <= now:
        raise HTTPException(400, "This password reset link is invalid or expired")
    user = await db.get(User, reset.user_id)
    if not user:
        raise HTTPException(400, "This password reset link is invalid or expired")
    user.password_hash = hash_password(data.password)
    reset.used_at = now
    await db.commit()
    return {"message": "Password reset successfully. You can now sign in with your new password."}


@auth.post("/register-organization", response_model=UserOut)
async def register_organization(data: OrganizationRegisterIn, db=Depends(get_db)):
    email = data.email.lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    org = Organization(
        name=data.organization_name,
        description=data.description,
        address=data.address,
        timezone=data.timezone,
    )
    db.add(org)
    await db.flush()
    user = User(
        name=data.name,
        email=email,
        password_hash=hash_password(data.password),
        role=Role.ORG_ADMIN,
        org_id=org.id,
    )
    db.add(user)
    await db.flush()
    await audit(db, org.id, user.id, "CREATE", "Organization", org.id)
    await db.commit()
    _cache_delete(_ORG_LIST_KEY)
    return user


@auth.post("/refresh", response_model=TokenOut)
async def refresh_ep(data: dict, db=Depends(get_db)):
    try:
        p = decode_token(data["refresh_token"])
        assert p["type"] == "refresh"
        u = await db.get(User, p["sub"])
    except Exception:
        raise HTTPException(401, "Invalid refresh token")
    return {
        "access_token": create_access_token(u.id, u.role.value),
        "refresh_token": create_refresh_token(u.id, u.role.value),
        "token_type": "bearer",
    }


@auth.post("/logout")
async def logout_ep(user=Depends(current_user)):
    return {"message": "Logged out; discard the client tokens."}


@auth.get("/me", response_model=UserOut)
async def me(user=Depends(current_user)):
    return user
