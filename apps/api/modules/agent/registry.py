"""The models a user can pick, and whether each one is usable."""
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
    provider: str  # nvidia | xai | anthropic | demo
    model: str
    api_key: str = ""
    base_url: str | None = None
    note: str | None = None

    @property
    def available(self) -> bool:
        return self.provider == "demo" or bool(self.api_key)


def model_options(settings: Settings | None = None) -> list[ModelOption]:
    s = settings or get_settings()
    options = [
        ModelOption(
            "nemotron", "NVIDIA Nemotron", "nvidia", s.nvidia_model, s.nvidia_api_key, s.nvidia_base_url,
            note="Open model, served by build.nvidia.com.",
        ),
        ModelOption("grok", "xAI Grok", "xai", s.xai_model, s.xai_api_key, s.xai_base_url),
        ModelOption("claude", "Anthropic Claude", "anthropic", s.anthropic_model, s.anthropic_api_key),
    ]
    if s.agent_enable_demo:
        options.append(ModelOption(
            "demo", "Demo (no LLM)", "demo", "scripted",
            note="A fixed investigation over live data; for UI work without model credits.",
        ))
    return options


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


async def check(option: ModelOption) -> tuple[bool, str]:
    """Ask the provider whether the key works and the configured model exists."""
    if option.provider == "demo":
        return True, "Scripted demo; no provider involved."
    if not option.api_key:
        return False, "No API key configured."

    if option.provider == "anthropic":
        client = anthropic.AsyncAnthropic(api_key=option.api_key)
        try:
            await client.models.retrieve(option.model)
        except anthropic.AuthenticationError:
            return False, "The Anthropic API key was rejected."
        except anthropic.NotFoundError:
            return False, f"Anthropic does not serve '{option.model}'."
        except anthropic.APIConnectionError:
            return False, "Cannot reach the Anthropic API."
        except anthropic.APIStatusError as exc:
            return False, f"Anthropic API error {exc.status_code}."
        return True, f"{option.model} is available."

    client = openai.AsyncOpenAI(api_key=option.api_key, base_url=option.base_url, timeout=30)
    try:
        ids = [m.id async for m in client.models.list()]
    except openai.AuthenticationError:
        return False, f"The {option.label} API key was rejected."
    except openai.APIConnectionError:
        return False, f"Cannot reach {option.base_url}."
    except openai.APIStatusError as exc:
        return False, f"{option.label} API error {exc.status_code}."
    if option.model not in ids:
        close = [i for i in ids if option.model.split("/")[-1].split("-")[0] in i][:8]
        hint = f" Similar ids: {', '.join(close)}." if close else ""
        return False, f"'{option.model}' is not in {option.label}'s model list.{hint}"
    return True, f"{option.model} is available."
