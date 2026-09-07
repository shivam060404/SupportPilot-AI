"""SQLAlchemy engine and session management for PostgreSQL."""
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db() -> Generator:
    """Dependency to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def check_database_connection() -> bool:
    """Return whether PostgreSQL is reachable without mutating schema."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


def init_db() -> None:
    """Compatibility hook for older callers; schema changes belong to Alembic."""
    check_database_connection()
