"""Database session management.

SQLite via SQLAlchemy, per the README technology stack. Two settings below are
deliberate and load-bearing for ADR-001 rather than defaults worth skimming:

1. `PRAGMA foreign_keys=ON` — SQLite does not enforce foreign keys unless asked.
   Without it, the ledger's `customer_id` and `order_id` references are
   advisory, and the audit trail Track C inherits can point at rows that never
   existed.

2. `BEGIN IMMEDIATE` on transaction start. This is the documented SQLAlchemy
   recipe for making SQLite serialize writers, and it closes the
   concurrent-redemption race named in ADR-001, Section 1, force 2. SQLite's
   default deferred transaction takes its write lock at first write, which
   leaves a window between reading a balance and appending the redemption that
   spends it: two requests can each read 100, each append -100, and leave the
   customer at -100. Taking the lock at BEGIN removes the window.

   The cost is that all writers serialize, which is acceptable at this scale.
   On PostgreSQL this would instead be a per-customer row lock
   (`SELECT ... FOR UPDATE`) or a serializable transaction with retry — see
   `app/services/rewards.py::lock_customer_for_redemption`.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base

DATABASE_URL = os.getenv("COFFEE_DB_URL", "sqlite:///./coffee.db")
_IS_SQLITE = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args=(
        # isolation_level=None disables the driver's own implicit transaction
        # handling so the BEGIN below is the one that counts.
        {"check_same_thread": False, "isolation_level": None} if _IS_SQLITE else {}
    ),
)

if _IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    @event.listens_for(engine, "begin")
    def _begin_immediate(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables.

    Sufficient at project scale. Any schema change landing on data another
    contributor holds requires a migration tool and a day-one-contract
    amendment, not a re-run of this function.
    """
    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session scoped to one request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
