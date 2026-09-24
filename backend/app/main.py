from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.investigations import router as investigations_router
from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Research-oriented multi-agent news claim verification system skeleton.",
)

app.include_router(health_router)
app.include_router(investigations_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "NewsFactCheck backend is running."}
