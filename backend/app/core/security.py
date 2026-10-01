from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt
from app.core.config import get_settings

ph = PasswordHasher()
settings = get_settings()

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False

def create_token(subject: str, role: str, token_type: str, expires_delta: timedelta):
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "role": role, "type": token_type, "iat": now, "exp": now + expires_delta}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def create_access_token(user_id, role):
    return create_token(str(user_id), role, "access", timedelta(minutes=settings.access_token_expire_minutes))

def create_refresh_token(user_id, role):
    return create_token(str(user_id), role, "refresh", timedelta(days=settings.refresh_token_expire_days))

def decode_token(token: str):
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
