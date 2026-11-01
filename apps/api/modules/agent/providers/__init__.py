from __future__ import annotations

from config import Settings
from modules.agent.providers.base import Agent
from modules.agent.registry import ModelOption


def build_agent(option: ModelOption, settings: Settings) -> Agent:
    """One agent per provider family. Each keeps its own native message history:
    converting Claude's turns to another format (or back) would drop the thinking
    blocks it needs echoed unchanged."""
    if option.provider == "anthropic":
        from modules.agent.providers.anthropic_agent import AnthropicAgent
        return AnthropicAgent(option, settings)
    if option.provider in ("nvidia", "meterless", "openai", "xai"):
        from modules.agent.providers.openai_compat_agent import OpenAICompatAgent
        return OpenAICompatAgent(option, settings)
    raise ValueError(f"No agent for provider '{option.provider}'")
