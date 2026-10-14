from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Models tried in order when the primary model is unavailable or rate-limited.
_DEFAULT_FALLBACK_MODELS = (
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
)


class Settings(BaseSettings):
    APP_NAME: str = "FactTrace API"
    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql+psycopg://newsfactcheck:change_me@localhost:5432/newsfactcheck"
    API_V1_PREFIX: str = "/api/v1"
    DEMO_MODE: bool = False

    POSTGRES_DB: str | None = None
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None
    FASTAPI_ENV: str = "development"
    NEXT_PUBLIC_API_URL: str | None = None

    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-3.1-flash-lite"
    #: Comma-separated list. Kept as a plain string so it parses identically
    #: whether it arrives from the environment, a .env file, or a test. Use
    #: ``llm_fallback_models()`` to read it as a list.
    LLM_FALLBACK_MODELS: str = ",".join(_DEFAULT_FALLBACK_MODELS)
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_MAX_ATTEMPTS: int = 3
    LLM_RETRY_BACKOFF_SECONDS: float = 1.5
    GEMINI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None

    #: Browser origins allowed to call the API, comma-separated. Never defaults
    #: to a wildcard: credentials are enabled, and a wildcard with credentials
    #: is rejected by browsers anyway.
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    #: Requests allowed per client IP per minute for the investigation endpoint.
    RATE_LIMIT_PER_MINUTE: int = 10

    GDELT_API_URL: str = "https://api.gdeltproject.org/api/v2/doc/doc"
    GDELT_MAX_RESULTS: int = 10
    GDELT_TIMESPAN_DAYS: int = 7
    GDELT_LANGUAGE: str = "en"
    GDELT_TIMEOUT_SECONDS: float = 10.0
    #: GDELT allows roughly one request every five seconds per client; requests
    #: are serialised to stay under this and retried briefly when they get a 429.
    GDELT_MIN_INTERVAL_SECONDS: float = 5.0
    GDELT_MAX_RETRIES: int = 2
    #: When GDELT keeps answering 429 (its per-IP limit is shared and can be
    #: exhausted for longer than one interval), stop calling it for a cooldown
    #: instead of burning the interval on every query. The breaker is process
    #: wide and closes automatically after the cooldown.
    GDELT_BREAKER_THRESHOLD: int = 3
    GDELT_BREAKER_COOLDOWN_SECONDS: float = 60.0

    #: Retrieval channels and queries are independent network calls, so they run
    #: concurrently. Channels that are intentionally serialised (GDELT's global
    #: throttle) still queue behind their own lock.
    RETRIEVAL_MAX_WORKERS: int = 4

    WEB_SEARCH_PROVIDER: str | None = None
    WEB_SEARCH_API_KEY: str | None = None
    WEB_SEARCH_ENDPOINT: str | None = None

    #: The primary-source channel reuses the web-search (Tavily) credentials by
    #: default; these settings override the endpoint and key when dedicated.
    PRIMARY_SOURCE_API_KEY: str | None = None
    PRIMARY_SOURCE_ENDPOINT: str | None = None
    PRIMARY_SOURCE_MAX_RESULTS: int = 5

    #: Fetch the full page text of the small primary-source shortlist so official
    #: records are adjudicated on their body rather than a search snippet. The
    #: fetch is best-effort: a failure keeps the snippet and never aborts a run.
    PRIMARY_FETCH_ENABLED: bool = True
    PRIMARY_FETCH_TIMEOUT_SECONDS: float = 15.0
    PRIMARY_FETCH_MAX_CHARS: int = 8000
    #: Minimum delay between page fetches; official sites are rate-sensitive.
    PRIMARY_FETCH_INTERVAL_SECONDS: float = 1.0

    # Evidence extraction controls
    EVIDENCE_MAX_DOCUMENTS_ASSESSED: int = 16
    EVIDENCE_SUBCLAIM_BATCH_SIZE: int = 4
    EVIDENCE_DOCUMENT_BATCH_SIZE: int = 4
    EVIDENCE_MIN_EXCERPT_CHARS: int = 40
    EVIDENCE_MAX_EXCERPT_CHARS: int = 4000

    SEARCH_MAX_QUERIES_PER_SUBCLAIM: int = 4
    SEARCH_MAX_RESULTS_PER_QUERY: int = 5
    OPPOSITION_MAX_RESULTS: int = 5

    # Crawler settings (full-page fetching for retrieval channels)
    CRAWLER_ENABLED: bool = True
    CRAWLER_TIMEOUT_SECONDS: float = 15.0
    CRAWLER_MAX_CHARS: int = 8000
    CRAWLER_MIN_INTERVAL_SECONDS: float = 2.0

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

    def cors_origins(self) -> list[str]:
        """Parse ``ALLOWED_ORIGINS`` into a list, tolerating an empty value."""
        return [origin.strip() for origin in (self.ALLOWED_ORIGINS or "").split(",") if origin.strip()]

    def llm_fallback_models(self) -> list[str]:
        """Parse ``LLM_FALLBACK_MODELS`` into a list.

        Falls back to the built-in defaults when the value is empty, so an
        unset or blank setting never disables fallback models.
        """
        value = (self.LLM_FALLBACK_MODELS or "").strip()
        if not value:
            return list(_DEFAULT_FALLBACK_MODELS)
        return [model.strip() for model in value.split(",") if model.strip()]


settings = Settings()
