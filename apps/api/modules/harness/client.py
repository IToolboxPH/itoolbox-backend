"""Client for the Zetaris platform API — the data harness.

Everything the agent knows about the data comes through here: which sources
exist, what their tables and columns are, and the rows a SELECT returns. Zetaris
federates the queries to the real databases, so nothing is copied out of them.

API shape (Zetaris 2.4.3.1, verified against a running instance):

    GET    /api/v1.0/auth/login                 Basic auth -> {idToken, refreshToken}
    GET    /api/v1.0/datasource/datasources     [{dataSourceId, name, description, tableCount}]
    GET    .../datasources/{id}/relations       [{dataSourceRelationId, name}]
    GET    .../datasources/{id}/relations/{table}/schema
    GET    /api/v1.0/lightning-database/databases
    POST   /api/v1.0/query/sql/start            {select, pageLimit<=100} -> first page + queryToken
    GET    /api/v1.0/query/sql/page             ?queryToken&pageLimit&pageNumber
    DELETE /api/v1.0/query/sql/close/{queryToken}

Every call carries X-Request-ID (a fresh UUID) and X-Org-ID.
"""
from __future__ import annotations

import asyncio
import re
import time
import uuid
from typing import Any

import httpx

from config import Settings, get_settings
from modules.harness.guard import check_read_only
from modules.harness.schemas import ColumnOut, HarnessStatus, QueryResult, SourceOut, TableOut

# Source and table metadata changes rarely; caching it keeps an investigation's
# discovery steps from paying a round trip each time.
_METADATA_TTL_SECONDS = 300
# Zetaris caps one page at 100 records.
_MAX_PAGE = 100


class ZetarisError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


_LITERAL = re.compile(r"'(?:[^']|'')*'|`[^`]*`")
_NAME = r"(?:`([^`]+)`|\"([^\"]+)\"|(\w+))"
_COLUMN = re.compile(rf"^(?:\w+\.)*{_NAME}$")
_ALIAS = re.compile(rf"(?:\bAS\s+|\s){_NAME}\s*$", re.IGNORECASE)


def _select_names(sql: str) -> list[str]:
    """Output column names of the outermost SELECT, in order, as far as a light scan can tell.

    Zetaris returns each row as a JSON object whose key order is not the SELECT's, and
    sends no column list, so the order is recovered from the query text. A name it
    cannot work out (SELECT *, an unaliased expression) just isn't listed.
    """
    masked = _LITERAL.sub(lambda m: "_" * len(m.group()), sql)
    depth, start, end = 0, None, len(masked)
    for m in re.finditer(r"[()]|\bselect\b|\bfrom\b", masked, re.IGNORECASE):
        token = m.group().lower()
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif depth == 0 and token == "select" and start is None:
            start = m.end()
        elif depth == 0 and token == "from" and start is not None:
            end = m.start()
            break
    if start is None:
        return []
    items, depth, last = [], 0, start
    for i in range(start, end):
        ch = masked[i]
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            items.append(sql[last:i])
            last = i + 1
    items.append(sql[last:end])
    names = []
    for item in items:
        item = re.sub(r"^\s*(?:distinct|all)\s+", "", item.strip(), flags=re.IGNORECASE)
        match = _COLUMN.match(item) or _ALIAS.search(item)
        if match:
            names.append(next(g for g in match.groups() if g is not None))
    return names


def _error_text(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        detail = body.get("message") or body.get("error") or body.get("detail") or body
    except ValueError:
        detail = resp.text
    detail = str(detail).strip() or resp.reason_phrase
    return f"Zetaris returned HTTP {resp.status_code}: {detail[:500]}"


class ZetarisClient:
    def __init__(self, settings: Settings):
        self.url = settings.zetaris_api_url.rstrip("/")
        self._org = str(settings.zetaris_org_id)
        self._api_key = settings.zetaris_api_key
        self._username = settings.zetaris_username
        self._password = settings.zetaris_password
        self._token: str | None = None
        self._lock = asyncio.Lock()
        self._cache: dict[str, tuple[float, Any]] = {}
        self._http = httpx.AsyncClient(base_url=self.url, timeout=settings.zetaris_timeout_seconds)

    # ── transport ────────────────────────────────────────────────────────────

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        return {"X-Request-ID": str(uuid.uuid4()), "X-Org-ID": self._org, **(extra or {})}

    async def _bearer(self, refresh: bool = False) -> str:
        if self._api_key:
            return self._api_key
        async with self._lock:
            if self._token and not refresh:
                return self._token
            if not (self._username and self._password):
                raise ZetarisError(
                    "Zetaris credentials are not configured: set ZETARIS_API_KEY, "
                    "or ZETARIS_USERNAME and ZETARIS_PASSWORD."
                )
            try:
                resp = await self._http.get(
                    "/api/v1.0/auth/login",
                    auth=(self._username, self._password),
                    headers=self._headers(),
                )
            except httpx.HTTPError as exc:
                raise ZetarisError(f"Cannot reach Zetaris at {self.url}: {exc}") from exc
            if resp.status_code != 200:
                raise ZetarisError(f"Zetaris sign-in failed: {_error_text(resp)}", resp.status_code)
            self._token = resp.json()["idToken"]
            return self._token

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        token = await self._bearer()
        try:
            resp = await self._http.request(
                method, path, headers=self._headers({"Authorization": f"Bearer {token}"}), **kwargs
            )
            # A login token expires; sign in again once. An API key has no refresh.
            if resp.status_code == 401 and not self._api_key:
                token = await self._bearer(refresh=True)
                resp = await self._http.request(
                    method, path, headers=self._headers({"Authorization": f"Bearer {token}"}), **kwargs
                )
        except httpx.TimeoutException as exc:
            raise ZetarisError("Zetaris did not answer in time; the query may be too heavy.") from exc
        except httpx.HTTPError as exc:
            raise ZetarisError(f"Cannot reach Zetaris at {self.url}: {exc}") from exc
        if resp.status_code >= 400:
            raise ZetarisError(_error_text(resp), resp.status_code)
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return resp.text

    async def _cached(self, key: str, loader) -> Any:
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < _METADATA_TTL_SECONDS:
            return hit[1]
        value = await loader()
        self._cache[key] = (time.monotonic(), value)
        return value

    # ── metadata ─────────────────────────────────────────────────────────────

    async def status(self) -> HarnessStatus:
        try:
            info = await self._request("GET", "/api/v1.0/utility/version")
        except ZetarisError as exc:
            return HarnessStatus(connected=False, url=self.url, error=str(exc))
        return HarnessStatus(
            connected=True,
            url=self.url,
            api_version=(info.get("apiVersion") or {}).get("version"),
            driver_version=(info.get("driverVersion") or {}).get("version"),
        )

    async def _datasources(self) -> list[dict[str, Any]]:
        return await self._cached(
            "datasources", lambda: self._request("GET", "/api/v1.0/datasource/datasources")
        ) or []

    async def list_sources(self) -> list[SourceOut]:
        sources = [
            SourceOut(
                name=d["name"],
                kind="datasource",
                description=d.get("description"),
                table_count=d.get("tableCount"),
            )
            for d in await self._datasources()
        ]
        databases = await self._cached(
            "lightning_databases", lambda: self._request("GET", "/api/v1.0/lightning-database/databases")
        ) or []
        sources += [
            SourceOut(
                name=d["name"],
                kind="lightning_database",
                description=d.get("description"),
                table_count=d.get("tableCount"),
            )
            for d in databases
        ]
        return sources

    async def _datasource_id(self, source: str) -> int:
        for d in await self._datasources():
            if d["name"].upper() == source.strip().upper():
                return d["dataSourceId"]
        known = ", ".join(d["name"] for d in await self._datasources()) or "none"
        raise ZetarisError(f"Unknown data source '{source}'. Registered data sources: {known}.", 404)

    async def list_tables(self, source: str) -> list[TableOut]:
        ds_id = await self._datasource_id(source)
        rows = await self._cached(
            f"tables:{ds_id}",
            lambda: self._request("GET", f"/api/v1.0/datasource/datasources/{ds_id}/relations"),
        ) or []
        return [TableOut(name=r["name"]) for r in rows]

    async def describe_table(self, source: str, table: str) -> list[ColumnOut]:
        ds_id = await self._datasource_id(source)
        name = table.strip().split(".")[-1]
        rows = await self._cached(
            f"columns:{ds_id}:{name.upper()}",
            lambda: self._request(
                "GET", f"/api/v1.0/datasource/datasources/{ds_id}/relations/{name}/schema"
            ),
        ) or []
        return [
            ColumnOut(
                # org_column_name is the source's own spelling (lowercase in Postgres).
                name=r.get("org_column_name") or r["column_name"],
                data_type=r.get("data_type") or r.get("jdbc_type_name") or "unknown",
                nullable=bool(r.get("nullable", True)),
                description=r.get("description"),
            )
            for r in rows
        ]

    # ── queries ──────────────────────────────────────────────────────────────

    async def run_sql(self, sql: str, max_rows: int) -> QueryResult:
        statement = check_read_only(sql)
        page_limit = max(1, min(max_rows, _MAX_PAGE))
        started = time.perf_counter()

        first = await self._request(
            "POST", "/api/v1.0/query/sql/start", json={"select": statement, "pageLimit": page_limit}
        )
        records: list[dict[str, Any]] = list(first.get("records") or [])
        token = first.get("queryToken")
        total_pages = int(first.get("totalPages") or 1)
        total_count = int(first.get("totalCount") or len(records))
        try:
            page = 1
            while token and len(records) < max_rows and page < total_pages:
                page += 1
                nxt = await self._request(
                    "GET",
                    "/api/v1.0/query/sql/page",
                    params={"queryToken": token, "pageLimit": page_limit, "pageNumber": page},
                )
                records.extend(nxt.get("records") or [])
        finally:
            if token:
                try:
                    await self._request("DELETE", f"/api/v1.0/query/sql/close/{token}")
                except ZetarisError:
                    pass  # the server expires abandoned queries on its own

        records = records[:max_rows]
        columns = list(records[0].keys()) if records else []
        # Back into SELECT order. Each value stays under its own key whatever the order,
        # and the sort is stable, so columns the scan couldn't name keep Zetaris's order.
        position: dict[str, int] = {}
        for i, name in enumerate(_select_names(statement)):
            position.setdefault(name.lower(), i)
        columns.sort(key=lambda c: position.get(c.lower(), len(position)))
        return QueryResult(
            sql=statement,
            columns=columns,
            rows=[[r.get(c) for c in columns] for r in records],
            row_count=total_count,
            truncated=total_count > len(records),
            elapsed_ms=int((time.perf_counter() - started) * 1000),
        )

    async def aclose(self) -> None:
        await self._http.aclose()


_client: ZetarisClient | None = None


def get_harness() -> ZetarisClient:
    global _client
    if _client is None:
        _client = ZetarisClient(get_settings())
    return _client
