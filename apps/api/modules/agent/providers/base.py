from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from modules.agent.tools import Emit, Toolbox


@dataclass
class AgentOutcome:
    status: Literal["completed", "failed", "refused"]
    answer: str | None = None
    error: str | None = None
    # ErrorEvent code when status is not completed.
    code: str | None = None


class ProviderError(Exception):
    """A model provider failed in a way the user should see (bad key, unknown model, outage)."""

    def __init__(self, message: str, code: str = "provider_error"):
        super().__init__(message)
        self.code = code


class Agent(Protocol):
    async def run(self, question: str, toolbox: Toolbox, emit: Emit) -> AgentOutcome: ...
