"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.analytics import router as analytics_router
from app.api.routes.assistant import router as assistant_router
from app.api.routes.upload import router as upload_router
from app.api.security import APIAccessMiddleware, require_access_token
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.session import get_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Configure process-level services at application startup."""
    settings = get_settings()
    configure_logging(settings.log_level)
    yield


LOGGER = logging.getLogger(__name__)
settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.2.0", lifespan=lifespan)
app.add_middleware(APIAccessMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(analytics_router, dependencies=[Depends(require_access_token)])
app.include_router(assistant_router, dependencies=[Depends(require_access_token)])
app.include_router(upload_router, dependencies=[Depends(require_access_token)])
app.mount(
    "/app",
    StaticFiles(directory=Path(__file__).resolve().parent / "static", html=True),
    name="dashboard",
)


@app.get("/", include_in_schema=False)
def dashboard() -> RedirectResponse:
    """Open the browser dashboard from the service root."""
    return RedirectResponse(url="/app/")


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Return a safe service-unavailable response for database failures."""
    LOGGER.error("api_database_error: %s", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Analytics database is unavailable"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Hide implementation details while retaining server-side diagnostics."""
    LOGGER.error("api_unhandled_error: %s", type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected server error occurred"},
    )


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


@app.middleware("http")
async def prevent_private_response_caching(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response
