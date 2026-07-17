"""SQLAlchemy engine and request-scoped session helpers."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create one pool-backed SQLAlchemy engine per process."""
    return create_engine(get_settings().sqlalchemy_database_url, pool_pre_ping=True)


def get_session_factory() -> sessionmaker[Session]:
    """Build a session factory bound to the cached engine."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_database_session() -> Generator[Session]:
    """Yield and reliably close one database session."""
    with get_session_factory()() as session:
        yield session
