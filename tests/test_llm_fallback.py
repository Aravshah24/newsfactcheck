import pytest

from app.config import settings
from app.services.llm import LLMClient, LLMConfigurationError


def test_quota_on_primary_model_falls_back_to_next_candidate(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FALLBACK_MODELS", "fallback-flash")
    client = LLMClient(provider="gemini", model="primary-flash")
    seen: list[str] = []

    def fake_dispatch(prompt, system_prompt, kwargs):
        seen.append(kwargs["model"])
        if kwargs["model"] == "primary-flash":
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")
        return "OK"

    monkeypatch.setattr(client, "_dispatch", fake_dispatch)

    assert client.generate("hi") == "OK"
    assert seen == ["primary-flash", "fallback-flash"]
    assert client.model == "fallback-flash"


def test_invalid_key_aborts_without_trying_fallbacks(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FALLBACK_MODELS", "fallback-flash")
    client = LLMClient(provider="gemini", model="primary-flash")
    seen: list[str] = []

    def fake_dispatch(prompt, system_prompt, kwargs):
        seen.append(kwargs["model"])
        raise RuntimeError("403 permission denied: API key not valid")

    monkeypatch.setattr(client, "_dispatch", fake_dispatch)

    with pytest.raises(LLMConfigurationError) as excinfo:
        client.generate("hi")

    assert excinfo.value.code == "LLM_INVALID_KEY"
    assert seen == ["primary-flash"]


def test_quota_on_all_models_reports_quota(monkeypatch):
    monkeypatch.setattr(settings, "LLM_FALLBACK_MODELS", "fallback-flash")
    client = LLMClient(provider="gemini", model="primary-flash")

    def fake_dispatch(prompt, system_prompt, kwargs):
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")

    monkeypatch.setattr(client, "_dispatch", fake_dispatch)

    with pytest.raises(LLMConfigurationError) as excinfo:
        client.generate("hi")

    assert excinfo.value.code == "LLM_QUOTA_EXHAUSTED"
