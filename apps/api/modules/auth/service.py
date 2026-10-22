from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.local_auth import decode_token, get_profile

bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_id = decode_token(credentials.credentials)
    return await get_profile(user_id, db)


def require_role(*roles: str):
    """FastAPI dependency that enforces global_role; super_admin always passes."""
    allowed = set(roles)

    async def _check(profile: dict = Depends(get_current_user)) -> dict:
        role = profile.get("global_role", "viewer")
        if role != "super_admin" and role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {sorted(allowed)}",
            )
        return profile

    return _check
