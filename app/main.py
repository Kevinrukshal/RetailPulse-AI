"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.session import get_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Configure process-level services at application startup."""
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


app = FastAPI(title=get_settings().app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health", tags=["Operations"])
def health() -> dict[str, str]:
    """Confirm that both the API process and PostgreSQL are available."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc
    return {"status": "ok", "database": "ok"}
