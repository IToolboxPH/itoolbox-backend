"""The models a user can pick, and whether each one is usable.

Every option is a real LLM from a provider. A model is listed even without
credentials, marked unavailable, so the picker shows what could be switched on.
"""
from __future__ import annotations

from dataclasses import dataclass

import anthropic
import openai
from fastapi import HTTPException, status

from config import Settings, get_settings


@dataclass(frozen=True)
class ModelOption:
    id: str
    label: str
    provider: str  # nvidia | meterless | openai | xai | anthropic
    model: str
    api_key: str = ""
    base_url: str | None = None
    note: str | None = None
    # Extra request headers, as pairs so the dataclass stays hashable.
    headers: tuple[tuple[str, str], ...] = ()

    @property
    def available(self) -> bool:
        return bool(self.api_key)


def model_options(settings: Settings | None = None) -> list[ModelOption]:
    s = settings or get_settings()
    return [
        ModelOption(
            "nemotron", "NVIDIA Nemotron", "nvidia", s.nvidia_model, s.nvidia_api_key, s.nvidia_base_url,
            note="Open model, served by build.nvidia.com.",
        ),
        ModelOption(
            "meterless", "Nemotron via Meterless", "meterless", s.meterless_model, s.meterless_runtime_token,
            s.meterless_base_url, note="Routed and receipted by Meterless Nightshift on this machine; needs Nightshift running.",
            # meterless-ttfb-ms: Nightshift stops a lane that sends no first token
            # within its cloud limit; an agent step with tool results can take longer.
            headers=(("meterless-app", "bantai"), ("meterless-scope", "user"), ("meterless-ttfb-ms", "120000")),
        ),
        ModelOption("gpt", "OpenAI GPT", "openai", s.openai_model, s.openai_api_key, s.openai_base_url),
        ModelOption("grok", "xAI Grok", "xai", s.xai_model, s.xai_api_key, s.xai_base_url),
        ModelOption("claude", "Anthropic Claude", "anthropic", s.anthropic_model, s.anthropic_api_key),
    ]


def default_model_id(settings: Settings | None = None) -> str:
    s = settings or get_settings()
    options = model_options(s)
    for o in options:
        if o.id == s.agent_default_model and o.available:
            return o.id
    usable = [o for o in options if o.available]
    return usable[0].id if usable else s.agent_default_model


def resolve(model_id: str | None) -> ModelOption:
    """The option to run, or a 400 the client can show."""
    wanted = model_id or default_model_id()
    for o in model_options():
        if o.id == wanted:
            if not o.available:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{o.label} is not configured on this server (no API key).",
                )
            return o
    known = ", ".join(o.id for o in model_options())
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown model '{wanted}'. Known: {known}.")


_PING = [{"role": "user", "content": "Reply with the single word: ready"}]


async def check(option: ModelOption) -> tuple[bool, str]:
    """Send the model one tiny real request.

    Listing models isn't enough: a valid key on an account without credits lists
    fine and fails on the first completion. This costs a few tokens.
    """
    if not option.api_key:
        return False, "No API key configured."

    if option.provider == "anthropic":
        client = anthropic.AsyncAnthropic(api_key=option.api_key, timeout=60)
        try:
            await client.messages.create(model=option.model, max_tokens=16, messages=_PING)
        except anthropic.AuthenticationError:
            return False, "The Anthropic API key was rejected."
        except anthropic.NotFoundError:
            return False, f"Anthropic does not serve '{option.model}'."
        except anthropic.APIConnectionError:
            return False, "Cannot reach the Anthropic API."
        except anthropic.APIStatusError as exc:
            return False, f"Anthropic API error {exc.status_code}: {exc.message}"
        return True, f"{option.model} answered."

    client = openai.AsyncOpenAI(
        api_key=option.api_key, base_url=option.base_url, timeout=120, max_retries=0,
        default_headers=dict(option.headers),
    )
    try:
        # No max_tokens: some providers reject it in favour of max_completion_tokens.
        await client.chat.completions.create(model=option.model, messages=_PING)
    except openai.AuthenticationError:
        return False, f"The {option.label} key was rejected."
    except openai.NotFoundError:
        return False, f"{option.label} does not serve '{option.model}'."
    except openai.APIConnectionError:
        return False, f"Cannot reach {option.base_url}."
    except openai.APIStatusError as exc:
        return False, f"{option.label} error {exc.status_code}: {exc.message}"
    return True, f"{option.model} answered."
