from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    # psycopg2 requires pool_pre_ping for serverless environments where
    # connections may be dropped between invocations.
    pool_pre_ping=True,
    # Vercel serverless: keep pool small to avoid connection exhaustion.
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: yields a DB session, closes it on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
