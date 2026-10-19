
from collections.abc import Generator

from sqlalchemy import create_engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import REPO_ROOT, get_settings


settings = get_settings()
url = make_url(settings.database_url)

if url.drivername.startswith("sqlite") and url.database not in (None, "", ":memory:"):
    # Anchor a relative SQLite file to the repository root so the same
    # database is used whether the server starts from the repo root or backend/.
    db_path = (REPO_ROOT / url.database).resolve()
    url = url.set(database=str(db_path))

if url.drivername.startswith("sqlite"):
    # SQLite needs this setting when used with FastAPI.
    connect_args = {"check_same_thread": False}
else:
    # Fail fast with a clear error instead of hanging when the database
    # server is unreachable (for example, Postgres is not running yet).
    connect_args = {"connect_timeout": 5}

engine = create_engine(
    url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy database models."""

    pass


def init_db() -> None:
    """Create any missing tables so a fresh checkout can serve requests."""
    from app import models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
