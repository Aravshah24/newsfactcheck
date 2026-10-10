from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.investigations import router as investigations_router
from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="0.2.0",
    description=(
        "Multi-agent news claim verification. Retrieval produces documents; evidence is "
        "assessed against the complete proposition; verdicts are weighted by source independence."
    ),
)

app.include_router(health_router)
app.include_router(investigations_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict:
    from app.retrievers.gdelt import GDELTRetriever
    from app.retrievers.primary_source import PrimarySourceRetriever
    from app.retrievers.web_search import WebSearchRetriever
    from app.services.llm import llm_diagnostics

    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "llm": llm_diagnostics(probe=False),
        "retrieval": {
            "gdelt": GDELTRetriever().is_available(),
            "web_search": WebSearchRetriever().is_available(),
            "primary_source": PrimarySourceRetriever().is_available(),
        },
    }


@app.get("/health/llm")
def llm_health() -> dict:
    """Live LLM check. Reports exactly what to fix when reasoning is unavailable."""
    from app.services.llm import llm_diagnostics

    return llm_diagnostics(probe=True)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "NewsFactCheck backend is running."}
