from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
import app.models  # noqa: F401


def _build_engine():
    try:
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 1},
            pool_timeout=2,
        )
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as exc:
        raise RuntimeError(
            "PostgreSQL is required for this application. Start the database and ensure DATABASE_URL points to the live Postgres instance."
        ) from exc


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()
