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
