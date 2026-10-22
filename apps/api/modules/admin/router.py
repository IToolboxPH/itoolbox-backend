"""User administration. Accounts are provisioned here by an admin; there is no
public sign-up."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth import local_auth
from modules.auth.router import UserProfileOut
from modules.auth.service import require_role

router = APIRouter(prefix="/users", tags=["admin"])

Role = Literal["super_admin", "admin", "analyst", "viewer"]


class CreateUserRequest(BaseModel):
    email: EmailStr
    full_name: str = ""
    password: str = Field(min_length=10)
    global_role: Role = "analyst"


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    global_role: Role | None = None
    is_active: bool | None = None


@router.get("", response_model=list[UserProfileOut])
async def list_users(
    _: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        text("SELECT id, email, full_name, global_role, is_active FROM user_profiles ORDER BY created_at")
    )).mappings().all()
    return [UserProfileOut(**{**r, "id": str(r["id"])}) for r in rows]


@router.post("", response_model=UserProfileOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    # Only a super_admin can mint another super_admin.
    if body.global_role == "super_admin" and actor.get("global_role") != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a super_admin can create super_admins")
    profile = await local_auth.create_user(body.email, body.full_name, body.password, body.global_role, db)
    return UserProfileOut(**profile)


@router.patch("/{user_id}", response_model=UserProfileOut)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    updates = body.model_dump(exclude_none=True)
    if updates.get("global_role") == "super_admin" and actor.get("global_role") != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only a super_admin can grant super_admin")
    if user_id == actor["id"] and updates.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot disable your own account")
    if updates:
        # Keys come from the whitelisted Pydantic model above, never from raw input.
        set_clause = ", ".join(f"{k} = :{k}" for k in updates)
        result = await db.execute(
            text(f"UPDATE user_profiles SET {set_clause}, updated_at = now() WHERE id = :id"),
            {**updates, "id": user_id},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    row = (await db.execute(
        text("SELECT id, email, full_name, global_role, is_active FROM user_profiles WHERE id = :id"),
        {"id": user_id},
    )).mappings().first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserProfileOut(**{**row, "id": str(row["id"])})
