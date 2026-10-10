"""Environment configuration. Secrets come from the environment, never source."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_MODEL = "openai/gpt-4o-mini"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MENTION = "@crabsweeper"
DEFAULT_MAX_COST_USD = 0.10
DEFAULT_MAX_OUTPUT_TOKENS = 1200
DEFAULT_SIZE_THRESHOLD = 400


@dataclass(frozen=True, slots=True)
class Route:
    """Pick a model by diff size: cheap/free for small, stronger for large."""

    small_model: str = ""
    large_model: str = ""
    threshold: int = DEFAULT_SIZE_THRESHOLD

    def choose(self, changed_lines: int, fallback: str) -> str:
        if changed_lines <= self.threshold:
            return self.small_model or fallback
        return self.large_model or fallback


@dataclass(frozen=True, slots=True)
class Budget:
    """A per-run ceiling: output tokens bound cost; `max_usd` caps the price."""

    max_usd: float = DEFAULT_MAX_COST_USD
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS


@dataclass(frozen=True, slots=True)
class Provider:
    """An OpenAI-compatible chat endpoint (OpenRouter, opencode, ...)."""

    base_url: str
    api_key: str
    model: str = ""
    route: Route = field(default_factory=Route)
    budget: Budget = field(default_factory=Budget)
    max_price: bool = False
    reasoning_effort: str = ""

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
    """`openrouter` has defaults; `opencode` and others are fully env-driven."""
    kind = env.get("CRABSWEEPER_LLM_PROVIDER", "openrouter").lower()
    return Provider(
        base_url=env.get("LLM_BASE_URL") or (OPENROUTER_BASE_URL if kind == "openrouter" else ""),
        api_key=env.get("LLM_API_KEY") or env.get("OPENROUTER_API_KEY", ""),
        model=_model(env, kind),
        route=Route(
            small_model=env.get("LLM_MODEL_SMALL", ""),
            large_model=env.get("LLM_MODEL_LARGE", ""),
            threshold=int(env.get("LLM_SIZE_THRESHOLD", str(DEFAULT_SIZE_THRESHOLD))),
        ),
        budget=Budget(
            max_usd=float(env.get("CRABSWEEPER_MAX_COST_USD", str(DEFAULT_MAX_COST_USD))),
            max_output_tokens=int(env.get("LLM_MAX_OUTPUT_TOKENS", str(DEFAULT_MAX_OUTPUT_TOKENS))),
        ),
        max_price=_enabled(env.get("CRABSWEEPER_ENFORCE_MAX_PRICE")),
        reasoning_effort=_reasoning_effort(env, kind),
    )


def _reasoning_effort(env: Mapping[str, str], kind: str) -> str:
    """Reasoning models burn the token budget thinking; keep it low by default."""
    if "LLM_REASONING_EFFORT" in env:
        return env["LLM_REASONING_EFFORT"]
    return "low" if kind == "openrouter" else ""


def _enabled(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes"}


def _model(env: Mapping[str, str], kind: str) -> str:
    explicit = env.get("LLM_MODEL")
    if explicit:
        return explicit
    fallback = env.get("LLM_MODEL_LARGE") or env.get("LLM_MODEL_SMALL") or ""
    return fallback or (DEFAULT_MODEL if kind == "openrouter" else "")


def _private_key(env: Mapping[str, str]) -> str:
    encoded = env.get("GITHUB_PRIVATE_KEY_BASE64", "")
    if encoded:
        return base64.b64decode(encoded).decode()
    return env.get("GITHUB_PRIVATE_KEY", "").replace("\\n", "\n")
