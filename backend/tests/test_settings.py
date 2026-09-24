from app.config import Settings


def test_settings_ignores_extra_env_keys() -> None:
    settings = Settings()
    assert settings.DATABASE_URL.startswith("postgresql+")
    assert settings.LLM_PROVIDER == "gemini"
