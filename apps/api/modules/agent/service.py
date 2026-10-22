"""Runs one investigation end to end and keeps its record.

The event trail is stored with the investigation exactly as it was streamed, so
GET /investigations/{id} can replay what the user watched.
"""
from __future__ import annotations

import asyncio
import re
import time
import traceback
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from config import get_settings
from database import AsyncSessionLocal
from modules.agent.models import Investigation
from modules.agent.providers import build_agent
from modules.agent.providers.base import ProviderError
from modules.agent.registry import ModelOption
from modules.agent.schemas import (
    AnswerEvent,
    DoneEvent,
    ErrorEvent,
    InvestigationDetail,
    InvestigationStartedEvent,
    InvestigationSummary,
)
from modules.agent.tools import Emit, Toolbox
from modules.harness.client import get_harness

_CITATION = re.compile(r"\[(E\d+)\]")


def _cited(answer: str | None, known: set[str]) -> list[str]:
    seen: list[str] = []
    for ref in _CITATION.findall(answer or ""):
        if ref in known and ref not in seen:
            seen.append(ref)
    return seen


def summary_of(row: Investigation) -> InvestigationSummary:
    return InvestigationSummary(
        id=str(row.id), question=row.question, model_id=row.model_id, model_name=row.model_name,
        status=row.status, tool_calls=row.tool_calls, duration_ms=row.duration_ms,
        created_at=row.created_at, finished_at=row.finished_at,
    )


def detail_of(row: Investigation) -> InvestigationDetail:
    return InvestigationDetail(
        **summary_of(row).model_dump(), answer=row.answer, error=row.error,
        events=row.events or [], evidence=row.evidence or [],
    )


async def run_investigation(question: str, option: ModelOption, user_id: str | None, emit: Emit) -> InvestigationDetail:
    settings = get_settings()
    started = time.perf_counter()
    events: list[dict] = []

    async def record(event: BaseModel) -> None:
        events.append(event.model_dump(mode="json"))
        await emit(event)

    async with AsyncSessionLocal() as db:
        row = Investigation(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id) if user_id else None,
            question=question,
            model_id=option.id,
            model_name=option.model,
            status="running",
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        await db.commit()

    toolbox = Toolbox(get_harness(), settings, record)
    status, answer, error = "failed", None, None
    try:
        await record(InvestigationStartedEvent(
            id=str(row.id), question=question, model=option.id, model_label=option.label, started_at=row.created_at,
        ))
        outcome = await build_agent(option, settings).run(question, toolbox, record)
        status, answer, error = outcome.status, outcome.answer, outcome.error
        if outcome.status == "completed":
            known = {e.id for e in toolbox.evidence}
            await record(AnswerEvent(markdown=outcome.answer or "", evidence_ids=_cited(outcome.answer, known)))
        else:
            await record(ErrorEvent(code=outcome.code or outcome.status,
                                    message=outcome.error or "The investigation did not finish."))
    except ProviderError as exc:
        status, error = "failed", str(exc)
        await record(ErrorEvent(code=exc.code, message=str(exc)))
    except asyncio.CancelledError:
        # The client went away. Keep the trail so far; nobody is left to stream to.
        status, error = "cancelled", "The client disconnected before the investigation finished."
        raise
    except Exception:
        status, error = "failed", "An unexpected error stopped the investigation."
        print(f"[agent] investigation {row.id} failed:\n{traceback.format_exc()}", flush=True)
        await record(ErrorEvent(code="internal_error", message=error))
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        if status != "cancelled":
            await record(DoneEvent(status=status, duration_ms=duration_ms, tool_calls=toolbox.calls))
        row.status, row.answer, row.error = status, answer, error
        row.events = events
        row.evidence = [e.model_dump(mode="json") for e in toolbox.evidence]
        row.tool_calls, row.duration_ms = toolbox.calls, duration_ms
        row.finished_at = datetime.now(timezone.utc)
        # Shielded so a cancelled request still records how far it got.
        await asyncio.shield(_save(row))

    return detail_of(row)


async def _save(row: Investigation) -> None:
    async with AsyncSessionLocal() as db:
        await db.merge(row)
        await db.commit()
