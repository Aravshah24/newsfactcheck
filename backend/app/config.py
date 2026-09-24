from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "NewsFactCheck API"
    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+psycopg://newsfactcheck:change_me@localhost:5432/newsfactcheck"
    API_V1_PREFIX: str = "/api/v1"


    POSTGRES_DB: str | None = None
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    FASTAPI_ENV: str = "development"
    NEXT_PUBLIC_API_URL: str | None = None

    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-2.5-flash"
    GEMINI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    GDELT_API_URL: str = "https://api.gdeltproject.org/api/v2/doc/doc"
    GDELT_MAX_RESULTS: int = 10
    GDELT_TIMESPAN_DAYS: int = 7
    GDELT_LANGUAGE: str = "en"
    GDELT_TIMEOUT_SECONDS: float = 10.0

    WEB_SEARCH_PROVIDER: str | None = None
    WEB_SEARCH_API_KEY: str | None = None
    WEB_SEARCH_ENDPOINT: str | None = None

    PRIMARY_SOURCE_PROVIDER: str | None = None
    PRIMARY_SOURCE_API_KEY: str | None = None
    PRIMARY_SOURCE_ENDPOINT: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def ensure_database_url(self):
        if not self.DATABASE_URL and self.POSTGRES_DB and self.POSTGRES_USER:
            password = self.POSTGRES_PASSWORD or "change_me"
            self.DATABASE_URL = f"postgresql+psycopg://{self.POSTGRES_USER}:{password}@localhost:5432/{self.POSTGRES_DB}"
        return self


settings = Settings()
