"""Database setup. SQLite for the POC; table and column names follow spec section 7.2 so the
move to PostgreSQL (composite tenant keys, PostGIS, revisions) is mechanical."""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_PATH = Path(os.environ.get("PLANOGRAM_DB", Path(__file__).resolve().parents[1] / "planogram.db"))
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - connection setup
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA journal_mode=WAL")
    cur.close()


SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@contextmanager
def unit_of_work() -> Iterator[Session]:
    """One request = one transaction: commit on success, roll back on any error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def use_engine(url: str) -> None:
    """Point the app at another database (tests)."""
    global engine
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _sqlite_pragmas)
    SessionLocal.configure(bind=engine)
