from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from apps.content_service.settings import load_settings


@lru_cache(maxsize=1)
def get_engine():
    settings = load_settings()
    return create_engine(settings.database_url, future=True, pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def get_db_session() -> Generator[Session, None, None]:
    ensure_content_service_schema()
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def ensure_content_service_schema() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE sources
                ADD COLUMN IF NOT EXISTS last_duration_ms INTEGER NULL
                """
            )
        )
