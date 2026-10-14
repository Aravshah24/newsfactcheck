from app.config import Settings


def test_settings_ignores_extra_env_keys() -> None:
    settings = Settings()
    assert settings.DATABASE_URL.startswith("postgresql+")
    assert settings.LLM_PROVIDER == "gemini"


def test_fallback_models_parse_comma_separated_value() -> None:
    settings = Settings(LLM_FALLBACK_MODELS="a-flash,b-flash,c-flash")
    assert settings.llm_fallback_models() == ["a-flash", "b-flash", "c-flash"]


def test_fallback_models_strip_whitespace_and_blank_entries() -> None:
    settings = Settings(LLM_FALLBACK_MODELS=" a , ,b ,")
    assert settings.llm_fallback_models() == ["a", "b"]


def test_fallback_models_default_when_empty() -> None:
    settings = Settings(LLM_FALLBACK_MODELS="")
    assert settings.llm_fallback_models() == [
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
    ]
