
from collections.abc import Generator

from sqlalchemy import create_engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import REPO_ROOT, get_settings


settings = get_settings()


def normalise_database_url(raw: str) -> str:
    """Accept URLs as hosting providers print them (postgres://, postgresql://) and use psycopg 3."""
    for prefix in ("postgres://", "postgresql://"):
        if raw.startswith(prefix):
            return "postgresql+psycopg://" + raw[len(prefix):]
    return raw


url = make_url(normalise_database_url(settings.database_url))

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


def init_db(bind=None) -> None:
    """Create missing tables, then apply versioned migrations for existing ones."""
    from app import models  # noqa: F401  (registers models on Base.metadata)
    from app.core.migrations import run_migrations

    target = bind or engine
    Base.metadata.create_all(bind=target)
    with target.begin() as conn:
        run_migrations(conn)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
