from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth import local_auth
from modules.auth.rate_limit import rate_limit
from modules.auth.service import get_current_user

router = APIRouter(tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    # Not EmailStr: sign-in only looks the address up, and format validation would
    # reject valid local accounts (e.g. a reserved domain like .local) before that.
    email: str = Field(min_length=3, max_length=320)
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10)


class UserProfileOut(BaseModel):
    # Always serialized in full, so defaulted fields are required in the contract.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: str
    email: str
    full_name: str = ""
    global_role: str = "viewer"
    is_active: bool = True


class TokenResponse(BaseModel):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    access_token: str
    token_type: str = "bearer"
    user: UserProfileOut


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit("login", 10, 300)),
):
    access_token, profile = await local_auth.login(body.email, body.password, db)
    return TokenResponse(access_token=access_token, user=UserProfileOut(**profile))


@router.get("/me", response_model=UserProfileOut)
async def me(profile: dict = Depends(get_current_user)):
    return UserProfileOut(**profile)


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    profile: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit("change-password", 5, 300)),
):
    await local_auth.change_password(profile["id"], body.current_password, body.new_password, db)
