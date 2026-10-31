"""The agent's tools: four calls into the data harness, shared by every model.

Toolbox.run is the single place a tool call is executed. It validates the
model's input, emits the tool_call / tool_result events the UI renders, and
numbers every successful query as evidence (E1, E2, ...) for the answer to cite.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from config import Settings
from modules.agent.schemas import Evidence, ToolCallEvent, ToolResultEvent
from modules.harness.client import ZetarisClient, ZetarisError
from modules.harness.guard import SqlRejected

Emit = Callable[[BaseModel], Awaitable[None]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


def _object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


_SOURCE = {"type": "string", "description": "Data source name, for example WEATHER"}

TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "list_sources",
        "List the data sources registered in Zetaris, with their descriptions and table counts.",
        _object({}, []),
    ),
    ToolSpec(
        "list_tables",
        "List the tables in one data source.",
        _object({"source": _SOURCE}, ["source"]),
    ),
    ToolSpec(
        "describe_table",
        "List a table's columns with their types and any catalog descriptions.",
        _object(
            {"source": _SOURCE, "table": {"type": "string", "description": "Table name, for example forecasts"}},
            ["source", "table"],
        ),
    ),
    ToolSpec(
        "run_sql",
        "Run one read-only Spark SQL query (SELECT, or WITH ... SELECT) through Zetaris. Reference "
        "tables as SOURCE.table, for example WEATHER.forecasts. The result gets an evidence id, like E3, "
        "that the answer must cite.",
        _object(
            {
                "sql": {"type": "string", "description": "A single read-only query, without a trailing semicolon"},
                "purpose": {
                    "type": "string",
                    "description": "One line saying what this query checks; shown to the user beside the result",
                },
            },
            ["sql", "purpose"],
        ),
    ),
)

_SPECS = {s.name: s for s in TOOL_SPECS}


def _validate(name: str, args: Any) -> str | None:
    """Check the model's input against the tool schema. Returns a problem, or None."""
    spec = _SPECS.get(name)
    if spec is None:
        return f"Unknown tool '{name}'. Available tools: {', '.join(_SPECS)}."
    if not isinstance(args, dict):
        return "Tool input must be a JSON object."
    for field in spec.parameters["required"]:
        value = args.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"'{field}' is required and must be a non-empty string."
    return None


class Toolbox:
    def __init__(self, harness: ZetarisClient, settings: Settings, emit: Emit):
        self._harness = harness
        self._emit = emit
        self._model_rows = settings.agent_model_row_limit
        self._evidence_rows = max(settings.agent_evidence_row_limit, settings.agent_model_row_limit)
        self.evidence: list[Evidence] = []
        self.calls = 0

    async def run(self, call_id: str, name: str, args: Any) -> tuple[str, bool]:
        """Execute one tool call. Returns (content for the model, is_error)."""
        self.calls += 1
        await self._emit(ToolCallEvent(call_id=call_id, tool=name, input=args if isinstance(args, dict) else {}))

        problem = _validate(name, args)
        if problem:
            return await self._fail(call_id, name, problem)
        try:
            if name == "list_sources":
                sources = await self._harness.list_sources()
                payload = [s.model_dump(exclude_none=True) for s in sources]
                await self._emit(ToolResultEvent(
                    call_id=call_id, tool=name, ok=True, summary=f"{len(sources)} data sources",
                ))
                return json.dumps(payload), False

            if name == "list_tables":
                tables = await self._harness.list_tables(args["source"])
                names = [t.name.lower() for t in tables]
                await self._emit(ToolResultEvent(
                    call_id=call_id, tool=name, ok=True,
                    summary=f"{len(names)} tables in {args['source'].upper()}",
                ))
                return json.dumps({"source": args["source"].upper(), "tables": names}), False

            if name == "describe_table":
                columns = await self._harness.describe_table(args["source"], args["table"])
                await self._emit(ToolResultEvent(
                    call_id=call_id, tool=name, ok=True,
                    summary=f"{len(columns)} columns in {args['source'].upper()}.{args['table'].lower()}",
                ))
                return json.dumps([c.model_dump(exclude_none=True) for c in columns]), False

            return await self._run_sql(call_id, args["sql"], args["purpose"])
        except SqlRejected as exc:
            return await self._fail(call_id, name, str(exc))
        except ZetarisError as exc:
            return await self._fail(call_id, name, str(exc))

    async def _run_sql(self, call_id: str, sql: str, purpose: str) -> tuple[str, bool]:
        result = await self._harness.run_sql(sql, self._evidence_rows)
        evidence = Evidence(
            id=f"E{len(self.evidence) + 1}",
            sql=result.sql,
            purpose=purpose,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            truncated=result.truncated,
            elapsed_ms=result.elapsed_ms,
        )
        self.evidence.append(evidence)
        await self._emit(ToolResultEvent(
            call_id=call_id,
            tool="run_sql",
            ok=True,
            summary=f"{evidence.id}: {result.row_count} row{'s' if result.row_count != 1 else ''}",
            evidence_id=evidence.id,
            sql=result.sql,
            purpose=purpose,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            truncated=result.truncated,
            elapsed_ms=result.elapsed_ms,
        ))
        shown = result.rows[: self._model_rows]
        payload: dict[str, Any] = {
            "evidence_id": evidence.id,
            "columns": result.columns,
            "rows": shown,
            "row_count": result.row_count,
        }
        if result.row_count > len(shown):
            payload["note"] = f"Showing {len(shown)} of {result.row_count} rows; aggregate to see the rest."
        return json.dumps(payload, default=str), False

    async def _fail(self, call_id: str, name: str, message: str) -> tuple[str, bool]:
        await self._emit(ToolResultEvent(call_id=call_id, tool=name, ok=False, summary=message, error=message))
        return json.dumps({"error": message}), True
