"""Nemotron (NVIDIA, direct or through Meterless), GPT (OpenAI) and Grok (xAI).

All of them serve OpenAI-compatible chat completions with function calling, so
one loop covers them; only the base URL, key, model id and headers differ.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

import openai

from config import Settings
from modules.agent.prompts import SYSTEM_PROMPT
from modules.agent.providers.base import AgentOutcome, ProviderError
from modules.agent.registry import ModelOption
from modules.agent.schemas import StatusEvent
from modules.agent.tools import TOOL_SPECS, Emit, Toolbox

# Reasoning models served this way may inline their reasoning as <think>...</think>.
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def _visible(text: str) -> str:
    return _THINK.sub("", text).strip()


class OpenAICompatAgent:
    def __init__(self, option: ModelOption, settings: Settings):
        self._label = option.label
        self._model = option.model
        self._max_steps = settings.agent_max_steps
        self._client = openai.AsyncOpenAI(
            api_key=option.api_key, base_url=option.base_url, timeout=180, max_retries=2,
            default_headers=dict(option.headers),
        )
        self._tools = [
            {"type": "function", "function": {"name": s.name, "description": s.description, "parameters": s.parameters}}
            for s in TOOL_SPECS
        ]

    async def _turn(self, messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, str]], str | None]:
        """Stream one completion. Returns (content, tool calls, finish_reason)."""
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=self._tools,
                tool_choice="auto",
                stream=True,
            )
            content: list[str] = []
            calls: dict[int, dict[str, str]] = {}
            finish: str | None = None
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta.content:
                    content.append(delta.content)
                for tc in delta.tool_calls or []:
                    slot = calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name and not slot["name"]:
                        slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["arguments"] += tc.function.arguments
                if choice.finish_reason:
                    finish = choice.finish_reason
        except openai.AuthenticationError:
            raise ProviderError(f"The {self._label} API key was rejected.", "auth")
        except openai.NotFoundError:
            raise ProviderError(f"{self._label} does not serve the model '{self._model}'.", "model_not_found")
        except openai.RateLimitError:
            raise ProviderError(f"{self._label}'s rate limit was reached; try again shortly.", "rate_limited")
        except openai.APIStatusError as exc:
            raise ProviderError(f"{self._label} API error {exc.status_code}: {exc.message}", "provider_error")
        except openai.APIConnectionError:
            raise ProviderError(f"Cannot reach the {self._label} API.", "provider_unreachable")
        except openai.APIError as exc:
            # An error event inside the stream, e.g. Meterless stopping a lane.
            raise ProviderError(f"{self._label} error: {exc.message}", "provider_error")

        ordered = [calls[i] for i in sorted(calls)]
        for call in ordered:
            call["id"] = call["id"] or f"call_{uuid.uuid4().hex[:12]}"
        return "".join(content), ordered, finish

    async def run(self, question: str, toolbox: Toolbox, emit: Emit) -> AgentOutcome:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        for _ in range(self._max_steps):
            content, calls, finish = await self._turn(messages)
            text = _visible(content)

            if not calls:
                if finish == "length":
                    return AgentOutcome("failed", answer=text or None,
                                        error="The answer was cut off at the output limit.", code="truncated")
                return AgentOutcome("completed", answer=text)

            if text:
                await emit(StatusEvent(text=text))
            messages.append({
                "role": "assistant",
                "content": content or None,
                "tool_calls": [
                    {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}}
                    for c in calls
                ],
            })
            for call in calls:
                try:
                    args: Any = json.loads(call["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = None  # Toolbox reports it back to the model as invalid input
                result, _is_error = await toolbox.run(call["id"], call["name"], args)
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

        return AgentOutcome("failed", error=f"Stopped after {self._max_steps} steps without a final answer.",
                            code="step_limit")
