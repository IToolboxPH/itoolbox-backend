"""Agent API contract, including the events POST /api/v1/agent/ask streams.

The stream is text/event-stream. Each message is

    event: <type>
    data: <one AgentEvent as JSON>

in this order: one `investigation`, then any number of `status`, `tool_call` and
`tool_result` (each tool_call is followed by the tool_result with the same
call_id), then `answer` or `error`, then exactly one `done`. Comment lines
(`: keep-alive`) arrive every 15 seconds of silence and carry no data.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel


class _Out(BaseModel):
    # Every field is always serialized, so the contract marks defaulted fields as
    # required (and nullable where they can be None). That keeps `type` a required
    # literal, which is what lets TypeScript narrow AgentEvent by it.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    # A model id from GET /api/v1/agent/models; the default model when omitted.
    model: str | None = None


class ModelInfo(_Out):
    id: str
    label: str
    provider: Literal["nvidia", "meterless", "openai", "xai", "anthropic"]
    model: str
    # Credentials are configured. Whether the provider accepts them is what
    # GET /models/{id}/check answers.
    available: bool
    default: bool
    note: str | None = None


class ModelCheck(_Out):
    id: str
    ok: bool
    detail: str


# ── Stream events ────────────────────────────────────────────────────────────

class InvestigationStartedEvent(_Out):
    type: Literal["investigation"] = "investigation"
    id: str
    question: str
    model: str
    model_label: str
    started_at: datetime


class StatusEvent(_Out):
    """A progress note from the agent: what it found, what it checks next."""
    type: Literal["status"] = "status"
    text: str


class ToolCallEvent(_Out):
    type: Literal["tool_call"] = "tool_call"
    call_id: str
    tool: str
    input: dict[str, Any]


class ToolResultEvent(_Out):
    """Outcome of one tool call. For run_sql, the rows are evidence the answer cites by evidence_id."""
    type: Literal["tool_result"] = "tool_result"
    call_id: str
    tool: str
    ok: bool
    summary: str
    evidence_id: str | None = None
    sql: str | None = None
    purpose: str | None = None
    columns: list[str] | None = None
    rows: list[list[Any]] | None = None
    row_count: int | None = None
    truncated: bool | None = None
    elapsed_ms: int | None = None
    error: str | None = None


class AnswerEvent(_Out):
    """The final answer, Markdown, citing evidence as [E1], [E2], ..."""
    type: Literal["answer"] = "answer"
    markdown: str
    evidence_ids: list[str]


class ErrorEvent(_Out):
    type: Literal["error"] = "error"
    # auth | model_not_found | rate_limited | provider_error | provider_unreachable |
    # refused | truncated | step_limit | harness_error | internal_error
    code: str
    message: str


class DoneEvent(_Out):
    type: Literal["done"] = "done"
    status: Literal["completed", "failed", "refused", "cancelled"]
    duration_ms: int
    tool_calls: int


AgentEventUnion = Annotated[
    Union[
        InvestigationStartedEvent,
        StatusEvent,
        ToolCallEvent,
        ToolResultEvent,
        AnswerEvent,
        ErrorEvent,
        DoneEvent,
    ],
    Field(discriminator="type"),
]


class AgentEvent(RootModel[AgentEventUnion]):
    """One server-sent event of POST /api/v1/agent/ask."""


# ── Investigations ───────────────────────────────────────────────────────────

class Evidence(_Out):
    id: str
    sql: str
    purpose: str | None = None
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    elapsed_ms: int


class InvestigationSummary(_Out):
    id: str
    question: str
    model_id: str
    model_name: str
    status: Literal["running", "completed", "failed", "refused", "cancelled"]
    tool_calls: int
    duration_ms: int | None = None
    created_at: datetime
    finished_at: datetime | None = None


class InvestigationDetail(InvestigationSummary):
    answer: str | None = None
    error: str | None = None
    events: list[AgentEventUnion]
    evidence: list[Evidence]
