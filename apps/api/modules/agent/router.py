from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.agent import registry
from modules.agent.models import Investigation
from modules.agent.schemas import AgentEvent, AskRequest, InvestigationDetail, InvestigationSummary, ModelCheck, ModelInfo
from modules.agent.service import detail_of, run_investigation, summary_of
from modules.auth.service import get_current_user, require_role

router = APIRouter(prefix="/agent", tags=["agent"])

_KEEPALIVE_SECONDS = 15
_ADMINS = {"super_admin", "admin"}


@router.get("/models", response_model=list[ModelInfo])
async def list_models(_: dict = Depends(get_current_user)):
    """The models the picker offers. `available` means credentials are configured."""
    default = registry.default_model_id()
    return [
        ModelInfo(id=o.id, label=o.label, provider=o.provider, model=o.model,
                  available=o.available, default=o.id == default, note=o.note)
        for o in registry.model_options()
    ]


@router.get("/models/{model_id}/check", response_model=ModelCheck)
async def check_model(model_id: str, _: dict = Depends(require_role("admin"))):
    """Ask the provider whether the key works and the configured model id exists."""
    option = next((o for o in registry.model_options() if o.id == model_id), None)
    if option is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown model '{model_id}'")
    ok, detail = await registry.check(option)
    return ModelCheck(id=model_id, ok=ok, detail=detail)


@router.post(
    "/ask",
    response_class=StreamingResponse,
    responses={
        200: {
            "model": AgentEvent,
            "description": "text/event-stream. Each `data:` line is one AgentEvent; see modules/agent/schemas.py.",
            "content": {"text/event-stream": {"schema": {"$ref": "#/components/schemas/AgentEvent"}}},
        }
    },
)
async def ask(body: AskRequest, user: dict = Depends(get_current_user)):
    """Investigate a question, streaming every step as it happens."""
    option = registry.resolve(body.model)
    queue: asyncio.Queue[BaseModel | None] = asyncio.Queue()

    async def emit(event: BaseModel) -> None:
        await queue.put(event)

    async def worker() -> None:
        try:
            await run_investigation(body.question, option, user["id"], emit)
        finally:
            await queue.put(None)

    task = asyncio.create_task(worker())

    async def stream():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_SECONDS)
                except asyncio.TimeoutError:
                    # A long query can be silent for a while; comments keep proxies
                    # (and Tailscale Serve) from closing the connection.
                    yield ": keep-alive\n\n"
                    continue
                if event is None:
                    break
                yield f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/investigations", response_model=InvestigationDetail)
async def investigate(body: AskRequest, user: dict = Depends(get_current_user)):
    """Investigate without streaming; returns when done. For scripts and QA."""
    option = registry.resolve(body.model)

    async def discard(_: BaseModel) -> None:
        return None

    return await run_investigation(body.question, option, user["id"], discard)


@router.get("/investigations", response_model=list[InvestigationSummary])
async def list_investigations(
    limit: int = Query(50, ge=1, le=200),
    everyone: bool = Query(False, description="Admins only: include other users' investigations"),
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Investigation).order_by(Investigation.created_at.desc()).limit(limit)
    if not (everyone and user.get("global_role") in _ADMINS):
        q = q.where(Investigation.user_id == uuid.UUID(user["id"]))
    rows = (await db.execute(q)).scalars().all()
    return [summary_of(r) for r in rows]


@router.get("/investigations/{investigation_id}", response_model=InvestigationDetail)
async def get_investigation(
    investigation_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Investigation, investigation_id)
    if row is None or (str(row.user_id) != user["id"] and user.get("global_role") not in _ADMINS):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investigation not found")
    return detail_of(row)
