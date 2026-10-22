"""Claude, through the Anthropic SDK.

A manual tool loop over the streaming beta Messages API, so every step can be
streamed to the UI and every tool call passes through the shared Toolbox:

- thinking {"type": "adaptive", "display": "updates"} (beta
  thinking-display-updates-2026-08-18): the short notes Claude writes between
  tool calls arrive as readable thinking text, shown as status events. Without
  it they come back empty and the UI goes quiet for the whole investigation.
- fallbacks="default" (beta server-side-fallback-2026-07-01): a request the
  model's safety classifiers decline is re-run server-side on the fallback model
  Anthropic recommends for that category, instead of ending the investigation.
- Assistant turns are appended exactly as returned, thinking blocks included.
  Editing or rebuilding earlier turns would invalidate those blocks.
- Tools stream their input as it is generated (eager_input_streaming), so the
  input is validated here (Toolbox) rather than by the server, and nothing runs
  for a turn that stopped on max_tokens or a refusal.
"""
from __future__ import annotations

from typing import Any

import anthropic

from config import Settings
from modules.agent.prompts import SYSTEM_PROMPT
from modules.agent.providers.base import AgentOutcome, ProviderError
from modules.agent.registry import ModelOption
from modules.agent.schemas import StatusEvent
from modules.agent.tools import TOOL_SPECS, Emit, Toolbox

_BETAS = ["thinking-display-updates-2026-08-18", "server-side-fallback-2026-07-01"]
# Thinking counts toward max_tokens even though its text is not returned.
_MAX_TOKENS = 64000
# Consecutive turns whose tool input could not be parsed at all.
_JSON_RETRIES = 2


class AnthropicAgent:
    def __init__(self, option: ModelOption, settings: Settings):
        self._client = anthropic.AsyncAnthropic(api_key=option.api_key)
        self._model = option.model
        self._effort = settings.anthropic_effort
        self._max_steps = settings.agent_max_steps
        self._tools = [
            {
                "name": s.name,
                "description": s.description,
                "input_schema": s.parameters,
                "eager_input_streaming": True,
            }
            for s in TOOL_SPECS
        ]

    async def _turn(self, messages: list[dict[str, Any]], emit: Emit):
        """Stream one model turn, emitting each progress note as its block completes."""
        notes: dict[int, list[str]] = {}
        async with self._client.beta.messages.stream(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            betas=_BETAS,
            fallbacks="default",
            thinking={"type": "adaptive", "display": "updates"},
            output_config={"effort": self._effort},
            # The system prompt and tools are byte-stable, so the growing
            # conversation reuses the cached prefix on every turn.
            cache_control={"type": "ephemeral"},
            system=SYSTEM_PROMPT,
            tools=self._tools,
            messages=messages,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_start" and event.content_block.type == "thinking":
                    notes[event.index] = []
                elif event.type == "content_block_delta" and event.delta.type == "thinking_delta":
                    notes.setdefault(event.index, []).append(event.delta.thinking)
                elif event.type == "content_block_stop" and event.index in notes:
                    note = "".join(notes.pop(event.index)).strip()
                    if note:
                        await emit(StatusEvent(text=note))
            return await stream.get_final_message()

    async def run(self, question: str, toolbox: Toolbox, emit: Emit) -> AgentOutcome:
        messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
        json_retries = 0

        for _ in range(self._max_steps):
            try:
                message = await self._turn(messages, emit)
                json_retries = 0
            except anthropic.AuthenticationError:
                raise ProviderError("The Anthropic API key was rejected.", "auth")
            except anthropic.NotFoundError:
                raise ProviderError(f"Anthropic does not serve the model '{self._model}'.", "model_not_found")
            except anthropic.RateLimitError:
                raise ProviderError("Anthropic's rate limit was reached; try again shortly.", "rate_limited")
            except anthropic.APIStatusError as exc:
                raise ProviderError(f"Anthropic API error {exc.status_code}: {exc.message}", "provider_error")
            except anthropic.APIConnectionError:
                raise ProviderError("Cannot reach the Anthropic API.", "provider_unreachable")
            except ValueError:
                # Tool-input JSON the SDK could not parse at all. The tool_use
                # block never completed, so there is no id to answer: re-issue.
                json_retries += 1
                if json_retries > _JSON_RETRIES:
                    return AgentOutcome("failed", error="Claude repeatedly produced unreadable tool input.",
                                        code="provider_error")
                continue

            messages.append({"role": "assistant", "content": message.content})

            if message.stop_reason == "refusal":
                category = getattr(message.stop_details, "category", None) if message.stop_details else None
                detail = f" (category: {category})" if category else ""
                return AgentOutcome("refused", error=f"Claude declined this request{detail}.", code="refused")
            if message.stop_reason == "pause_turn":
                continue

            tool_uses = [b for b in message.content if b.type == "tool_use"]
            text = "".join(b.text for b in message.content if b.type == "text").strip()

            if not tool_uses:
                if message.stop_reason == "max_tokens":
                    return AgentOutcome("failed", answer=text or None,
                                        error="The answer was cut off at the output limit.", code="truncated")
                return AgentOutcome("completed", answer=text)
            if message.stop_reason == "max_tokens":
                # A truncated tool input still parses as a partial object; never run it.
                return AgentOutcome("failed", error="A tool call was cut off at the output limit.", code="truncated")

            if text:
                await emit(StatusEvent(text=text))

            # All results go back in one user message, matching the parallel tool_use blocks.
            results = []
            for block in tool_uses:
                content, is_error = await toolbox.run(block.id, block.name, block.input)
                result: dict[str, Any] = {"type": "tool_result", "tool_use_id": block.id, "content": content}
                if is_error:
                    result["is_error"] = True
                results.append(result)
            messages.append({"role": "user", "content": results})

        return AgentOutcome("failed", error=f"Stopped after {self._max_steps} steps without a final answer.",
                            code="step_limit")
