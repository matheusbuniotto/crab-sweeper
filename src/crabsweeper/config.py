"""Environment configuration. Secrets come from the environment, never source."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_MODEL = "openai/gpt-4o-mini"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MENTION = "@crabsweeper"


@dataclass(frozen=True, slots=True)
class Provider:
    """An OpenAI-compatible chat endpoint (OpenRouter, opencode-go, ...)."""

    base_url: str
    api_key: str
    model: str

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


@dataclass(frozen=True, slots=True)
class Settings:
    app_id: str
    private_key: str
    webhook_secret: str
    provider: Provider
    mention: str
    port: int

    @property
    def github_configured(self) -> bool:
        return bool(self.app_id and self.private_key and self.webhook_secret)


def settings_from_env(env: Mapping[str, str]) -> Settings:
    return Settings(
        app_id=env.get("GITHUB_APP_ID", ""),
        private_key=_private_key(env),
        webhook_secret=env.get("GITHUB_WEBHOOK_SECRET", ""),
        provider=provider_from_env(env),
        mention=env.get("CRABSWEEPER_MENTION", DEFAULT_MENTION),
        port=int(env.get("PORT", "8000")),
    )


def provider_from_env(env: Mapping[str, str]) -> Provider:
    """`openrouter` has defaults; every other gateway is fully env-driven."""
    if env.get("CRABSWEEPER_LLM_PROVIDER", "openrouter").lower() == "openrouter":
        return Provider(
            base_url=env.get("LLM_BASE_URL") or OPENROUTER_BASE_URL,
            api_key=env.get("LLM_API_KEY") or env.get("OPENROUTER_API_KEY", ""),
            model=env.get("LLM_MODEL") or DEFAULT_MODEL,
        )
    return Provider(
        base_url=env.get("LLM_BASE_URL", ""),
        api_key=env.get("LLM_API_KEY", ""),
        model=env.get("LLM_MODEL", ""),
    )


def _private_key(env: Mapping[str, str]) -> str:
    encoded = env.get("GITHUB_PRIVATE_KEY_BASE64", "")
    if encoded:
        return base64.b64decode(encoded).decode()
    return env.get("GITHUB_PRIVATE_KEY", "").replace("\\n", "\n")
