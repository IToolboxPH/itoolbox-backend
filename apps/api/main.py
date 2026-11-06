"""IToolbox Platform API — unified FastAPI backend."""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import get_settings
from database import AsyncSessionLocal
from modules.admin.router import router as admin_router
from modules.agent.router import router as agent_router
from modules.auth import local_auth
from modules.auth.router import router as auth_router
from modules.harness.client import get_harness
from modules.harness.router import router as harness_router

settings = get_settings()
VERSION = "0.1.0"


def _run_migrations() -> None:
    print("[startup] Running alembic upgrade head ...", flush=True)
    env = {**os.environ, "DATABASE_URL": settings.database_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
        env=env,
    )
    if result.returncode != 0:
        print(f"[startup] Migration exited with code {result.returncode}", flush=True)
    else:
        print("[startup] Migration complete.", flush=True)


async def _bootstrap_admin() -> None:
    """Create the first super_admin from SEED_ADMIN_* when there are no users yet."""
    if not (settings.seed_admin_email and settings.seed_admin_password):
        return
    async with AsyncSessionLocal() as db:
        users = (await db.execute(text("SELECT count(*) FROM user_profiles"))).scalar_one()
        if users:
            return
        await local_auth.create_user(
            settings.seed_admin_email, settings.seed_admin_name, settings.seed_admin_password, "super_admin", db,
        )
        await db.commit()
    print(f"[startup] Created super_admin {settings.seed_admin_email}", flush=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.jwt_secret == "change-me":
        print("[startup] WARNING: JWT_SECRET is the placeholder; set a long random value in .env.", flush=True)
    _run_migrations()
    try:
        await _bootstrap_admin()
    except Exception as exc:
        print(f"[startup] Admin bootstrap skipped: {exc}", flush=True)
    yield
    await get_harness().aclose()


app = FastAPI(
    title="IToolbox Platform API",
    description=(
        "Backend for the IToolbox Ecosystem Platform.\n\n"
        "**Modules:**\n"
        "- **Auth / Admin**: local JWT sign-in; accounts are provisioned by an admin\n"
        "- **Data Harness**: governed, read-only access to live data (sources, tables, columns, "
        "SELECT queries); nothing is copied out of the source databases\n"
        "- **Agent (BantAI)**: IToolbox's AI assistant; answers questions about the platform and from "
        "live data, citing the queries behind every claim; the model is picked per question\n\n"
        "**API route prefixes:** `/api/v1/auth` · `/api/v1/admin` · `/api/v1/harness` · `/api/v1/agent`"
    ),
    version=VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

origins = (
    [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    if settings.platform_env != "local"
    else ["*"]
)
if settings.platform_env != "local" and (not origins or origins == ["*"]):
    print(
        "[startup] WARNING: ALLOWED_ORIGINS is not set to explicit origins in a non-local "
        "environment. Set it to the deployed itoolbox-frontend origin(s).",
        flush=True,
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    # Bearer tokens travel in the Authorization header, not cookies.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,    prefix="/api/v1/auth")
app.include_router(admin_router,   prefix="/api/v1/admin")
app.include_router(harness_router, prefix="/api/v1")
app.include_router(agent_router,   prefix="/api/v1")


@app.get("/api/v1/health", tags=["health"])
async def health():
    return {"status": "ok", "env": settings.platform_env, "version": VERSION}


@app.get("/", tags=["root"])
async def root():
    return {
        "name": "IToolbox Platform API",
        "version": VERSION,
        "routes": ["auth", "admin", "harness", "agent"],
        "docs": "/docs",
    }
