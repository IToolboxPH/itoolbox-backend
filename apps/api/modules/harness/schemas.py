from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    # Always serialized in full, so defaulted fields are required in the contract.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class HarnessStatus(_Out):
    connected: bool
    url: str
    api_version: str | None = None
    driver_version: str | None = None
    error: str | None = None


class SourceOut(_Out):
    name: str
    # datasource: a registered JDBC source (your databases); lightning_database:
    # data Zetaris holds pointers to itself (the bundled samples).
    kind: Literal["datasource", "lightning_database"]
    description: str | None = None
    table_count: int | None = None


class TableOut(_Out):
    name: str


class ColumnOut(_Out):
    name: str
    data_type: str
    nullable: bool = True
    description: str | None = None


class QueryRequest(BaseModel):
    sql: str = Field(min_length=1, max_length=20_000)
    max_rows: int = Field(default=100, ge=1, le=500)


class QueryResult(_Out):
    sql: str
    columns: list[str]
    rows: list[list[Any]]
    # Total rows the query produced; rows holds at most max_rows of them.
    row_count: int
    truncated: bool
    elapsed_ms: int
