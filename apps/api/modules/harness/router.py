from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from modules.auth.service import get_current_user, require_role
from modules.harness.client import ZetarisError, get_harness
from modules.harness.guard import SqlRejected
from modules.harness.schemas import ColumnOut, HarnessStatus, QueryRequest, QueryResult, SourceOut, TableOut

router = APIRouter(prefix="/harness", tags=["data-harness"])


def _http_error(exc: ZetarisError) -> HTTPException:
    # A 404 from Zetaris (unknown source/table) stays a 404; anything else is the
    # upstream failing, which is a 502 from this API's point of view.
    code = status.HTTP_404_NOT_FOUND if exc.status_code == 404 else status.HTTP_502_BAD_GATEWAY
    return HTTPException(status_code=code, detail=str(exc))


@router.get("/status", response_model=HarnessStatus)
async def harness_status(_: dict = Depends(get_current_user)) -> HarnessStatus:
    """Whether this API can reach Zetaris, and which version it runs."""
    return await get_harness().status()


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(_: dict = Depends(get_current_user)):
    try:
        return await get_harness().list_sources()
    except ZetarisError as exc:
        raise _http_error(exc)


@router.get("/sources/{source}/tables", response_model=list[TableOut])
async def list_tables(source: str, _: dict = Depends(get_current_user)):
    try:
        return await get_harness().list_tables(source)
    except ZetarisError as exc:
        raise _http_error(exc)


@router.get("/sources/{source}/tables/{table}", response_model=list[ColumnOut])
async def describe_table(source: str, table: str, _: dict = Depends(get_current_user)):
    try:
        return await get_harness().describe_table(source, table)
    except ZetarisError as exc:
        raise _http_error(exc)


@router.post("/query", response_model=QueryResult)
async def run_query(body: QueryRequest, _: dict = Depends(require_role("admin", "analyst"))):
    """Run one read-only SELECT through Zetaris. Used to re-run an agent's evidence query."""
    try:
        return await get_harness().run_sql(body.sql, body.max_rows)
    except SqlRejected as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ZetarisError as exc:
        raise _http_error(exc)
