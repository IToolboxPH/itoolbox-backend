"""Local auth — passwords hashed into user_credentials, HS256 JWTs signed with
settings.jwt_secret. No external identity provider is involved.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

import bcrypt as _bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings

settings = get_settings()

_TOKEN_TTL = settings.access_token_expire_minutes * 60


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


def issue_token(user_id: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "iat": now, "exp": now + _TOKEN_TTL}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str:
    """Verify the JWT and return its subject (user id). Raises 401 on failure."""
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject")
    return user_id


def _profile_dict(row: Any) -> dict[str, Any]:
    return {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in dict(row).items()}


async def get_profile(user_id: str, db: AsyncSession) -> dict[str, Any]:
    """Fetch user_profiles row by id. Raises 401 if missing, 403 if disabled."""
    row = (await db.execute(
        text("SELECT * FROM user_profiles WHERE id = :id"),
        {"id": user_id},
    )).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User profile not found")
    profile = _profile_dict(row)
    if not profile.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return profile


async def login(email: str, password: str, db: AsyncSession) -> tuple[str, dict[str, Any]]:
    """Verify credentials and return (access_token, profile)."""
    cred = (await db.execute(
        text("SELECT user_id, hashed_password FROM user_credentials WHERE email = :email"),
        {"email": email.lower()},
    )).mappings().first()
    if not cred or not verify_password(password, cred["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    profile = await get_profile(str(cred["user_id"]), db)
    return issue_token(str(cred["user_id"])), profile


async def create_user(
    email: str, full_name: str, password: str, global_role: str, db: AsyncSession
) -> dict[str, Any]:
    """Insert user_profiles + user_credentials. Caller commits."""
    email = email.lower()
    exists = (await db.execute(
        text("SELECT 1 FROM user_profiles WHERE email = :email"), {"email": email}
    )).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    new_id = str(uuid.uuid4())
    await db.execute(
        text("""
            INSERT INTO user_profiles (id, email, full_name, global_role, is_active)
            VALUES (:id, :email, :full_name, :role, TRUE)
        """),
        {"id": new_id, "email": email, "full_name": full_name, "role": global_role},
    )
    await db.execute(
        text("INSERT INTO user_credentials (user_id, email, hashed_password) VALUES (:id, :email, :pw)"),
        {"id": new_id, "email": email, "pw": hash_password(password)},
    )
    return await get_profile(new_id, db)


async def change_password(user_id: str, current: str, new: str, db: AsyncSession) -> None:
    cred = (await db.execute(
        text("SELECT hashed_password FROM user_credentials WHERE user_id = :id"), {"id": user_id}
    )).mappings().first()
    if not cred or not verify_password(current, cred["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    await db.execute(
        text("UPDATE user_credentials SET hashed_password = :pw, updated_at = now() WHERE user_id = :id"),
        {"pw": hash_password(new), "id": user_id},
    )
