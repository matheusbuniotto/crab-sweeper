"""Provider selection is env-driven so any OpenAI-compatible gateway works."""

from crabsweeper.config import provider_from_env, settings_from_env


def test_openrouter_is_the_default_provider() -> None:
    provider = provider_from_env({"OPENROUTER_API_KEY": "k"})
    assert provider.base_url == "https://openrouter.ai/api/v1"
    assert provider.model
    assert provider.configured is True


def test_another_gateway_is_fully_env_driven() -> None:
    provider = provider_from_env(
        {
            "CRABSWEEPER_LLM_PROVIDER": "opencode",
            "LLM_BASE_URL": "https://gateway.example/v1",
            "LLM_API_KEY": "k",
            "LLM_MODEL": "some/model",
        }
    )
    assert (provider.base_url, provider.api_key, provider.model) == (
        "https://gateway.example/v1",
        "k",
        "some/model",
    )


def test_a_missing_key_leaves_the_provider_unconfigured() -> None:
    assert provider_from_env({}).configured is False


def test_the_private_key_accepts_escaped_newlines() -> None:
    settings = settings_from_env({"GITHUB_PRIVATE_KEY": "line1\\nline2"})
    assert settings.private_key == "line1\nline2"


def test_small_diffs_use_the_cheap_model() -> None:
    provider = provider_from_env(
        {
            "CRABSWEEPER_LLM_PROVIDER": "opencode",
            "LLM_BASE_URL": "https://gateway.example/v1",
            "LLM_API_KEY": "k",
            "LLM_MODEL_SMALL": "free/auto",
            "LLM_MODEL_LARGE": "gpt-6-luna",
            "LLM_SIZE_THRESHOLD": "100",
        }
    )
    assert provider.route.choose(50, provider.model) == "free/auto"
    assert provider.route.choose(500, provider.model) == "gpt-6-luna"


def test_the_per_run_budget_is_configurable() -> None:
    provider = provider_from_env({"OPENROUTER_API_KEY": "k", "CRABSWEEPER_MAX_COST_USD": "0.10"})
    assert provider.budget.max_usd == 0.10
    assert provider.budget.max_output_tokens == 1200


def test_openrouter_defaults_to_low_reasoning_effort() -> None:
    assert provider_from_env({"OPENROUTER_API_KEY": "k"}).reasoning_effort == "low"


def test_reasoning_effort_can_be_overridden_or_disabled() -> None:
    overridden = provider_from_env({"OPENROUTER_API_KEY": "k", "LLM_REASONING_EFFORT": "high"})
    disabled = provider_from_env({"OPENROUTER_API_KEY": "k", "LLM_REASONING_EFFORT": ""})
    assert overridden.reasoning_effort == "high"
    assert disabled.reasoning_effort == ""
