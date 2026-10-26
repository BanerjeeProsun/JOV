"""Database engine, connection lifecycle, and session factory."""

from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from jovsi.config import settings
from jovsi.adapters.db.models import Base
from jovsi.adapters.db.triggers import apply_immutability_triggers


def create_db_engine(url: str = settings.DATABASE_URL) -> Engine:
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(url, connect_args=connect_args)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(target_engine: Engine = engine) -> None:
    """Create all tables, perform lightweight migrations, and attach immutability triggers."""
    Base.metadata.create_all(bind=target_engine)
    with target_engine.begin() as conn:
        try:
            res = conn.exec_driver_sql("PRAGMA table_info(candidates)").fetchall()
            col_names = [r[1] for r in res]
            if col_names and "user_id" not in col_names:
                conn.exec_driver_sql("ALTER TABLE candidates ADD COLUMN user_id VARCHAR(36) REFERENCES users(id)")
        except Exception:
            pass
        apply_immutability_triggers(conn)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
