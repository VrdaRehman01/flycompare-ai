"""Lightweight, versioned schema migrations.

New tables are created by ``Base.metadata.create_all``. Changes to tables that
may already hold records (for example adding columns) live here, run once, and
are recorded in ``schema_migrations``. Each step is written to be safe on both
SQLite and PostgreSQL and to leave existing rows valid.
"""

import re
from collections.abc import Callable

from sqlalchemy import Connection, inspect, text

_CODE_RE = re.compile(r"\(([A-Za-z]{3})\)\s*$")


def _code_from_label(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if re.fullmatch(r"[A-Za-z]{3}", value):
        return value.upper()
    match = _CODE_RE.search(value)
    return match.group(1).upper() if match else None


def _add_missing_columns(conn: Connection, table: str, columns: dict[str, str]) -> None:
    existing = {col["name"] for col in inspect(conn).get_columns(table)}
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def m0001_search_history_context(conn: Connection) -> None:
    """Link searches to users and record normalised airport codes and fare summary."""
    _add_missing_columns(
        conn,
        "flight_search_history",
        {
            "user_id": "INTEGER",
            "origin_code": "VARCHAR(3)",
            "destination_code": "VARCHAR(3)",
            "provider": "VARCHAR(50)",
            "data_status": "VARCHAR(10)",
            "currency": "VARCHAR(3)",
            "min_price": "FLOAT",
        },
    )
    # Backfill airport codes for older rows that stored labels such as "Karachi (KHI)".
    # Free-text values without a code (for example "Japan") are left as NULL.
    rows = conn.execute(
        text("SELECT id, origin, destination FROM flight_search_history WHERE origin_code IS NULL OR destination_code IS NULL")
    ).all()
    for row_id, origin, destination in rows:
        conn.execute(
            text("UPDATE flight_search_history SET origin_code = :o, destination_code = :d WHERE id = :id"),
            {"o": _code_from_label(origin), "d": _code_from_label(destination), "id": row_id},
        )
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_flight_search_history_user_id ON flight_search_history (user_id)"))


def m0002_passengers_multicity_connections(conn: Connection) -> None:
    """Child/infant counts and multi-city legs on searches; connection airports on observations."""
    _add_missing_columns(
        conn,
        "flight_search_history",
        {"children": "INTEGER NOT NULL DEFAULT 0", "infants": "INTEGER NOT NULL DEFAULT 0", "legs": "JSON"},
    )
    _add_missing_columns(conn, "fare_observations", {"connections": "VARCHAR(40)"})


def m0003_destination_image_sources(conn: Connection) -> None:
    """Record the photo source and a high-DPI thumbnail; retry earlier "no photo" results.

    Lookups before this version rejected many valid photos (hyphenated licence names,
    thumbnail file names), so cached negatives are expired rather than trusted.
    """
    _add_missing_columns(conn, "destination_images", {"url_2x": "VARCHAR(600)", "source": "VARCHAR(40)"})
    conn.execute(text("UPDATE destination_images SET source = 'Wikipedia' WHERE status = 'ok' AND source IS NULL"))
    conn.execute(text("UPDATE destination_images SET fetched_at = :old WHERE status <> 'ok'"), {"old": "2000-01-01 00:00:00"})


def m0004_observation_airline_identity(conn: Connection) -> None:
    """Airline code and logo on fare observations; earlier rows keep NULL (shown as initials)."""
    _add_missing_columns(conn, "fare_observations", {"airline_code": "VARCHAR(3)", "airline_logo_url": "VARCHAR(300)"})


MIGRATIONS: list[tuple[str, Callable[[Connection], None]]] = [
    ("0001_search_history_context", m0001_search_history_context),
    ("0002_passengers_multicity_connections", m0002_passengers_multicity_connections),
    ("0003_destination_image_sources", m0003_destination_image_sources),
    ("0004_observation_airline_identity", m0004_observation_airline_identity),
]


def run_migrations(conn: Connection) -> list[str]:
    conn.execute(
        text("CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(100) PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    )
    applied = {row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))}
    ran: list[str] = []
    for version, migrate in MIGRATIONS:
        if version in applied:
            continue
        migrate(conn)
        conn.execute(text("INSERT INTO schema_migrations (version) VALUES (:v)"), {"v": version})
        ran.append(version)
    return ran
