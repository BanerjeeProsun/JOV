"""Database engine, connection lifecycle, and session factory."""

from datetime import datetime
from typing import Generator
import uuid
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

        try:
            # Seed default job sources registry if empty
            count = conn.exec_driver_sql("SELECT COUNT(*) FROM job_sources").scalar()
            if count == 0:
                now_iso = datetime.utcnow().isoformat()
                default_sources = [
                    (str(uuid.uuid4()), "greenhouse", "Cloudflare", "cloudflare", "untested", 0, now_iso, now_iso),
                    (str(uuid.uuid4()), "greenhouse", "Figma", "figma", "untested", 0, now_iso, now_iso),
                    (str(uuid.uuid4()), "greenhouse", "Stripe", "stripe", "untested", 0, now_iso, now_iso),
                    (str(uuid.uuid4()), "greenhouse", "Canonical", "canonical", "untested", 0, now_iso, now_iso),
                    (str(uuid.uuid4()), "lever", "Palantir", "palantir", "untested", 0, now_iso, now_iso),
                    (str(uuid.uuid4()), "lever", "Lever Demo", "leverdemo", "untested", 0, now_iso, now_iso),
                    (str(uuid.uuid4()), "ashby", "Ramp", "ramp", "untested", 0, now_iso, now_iso),
                    (str(uuid.uuid4()), "ashby", "Linear", "linear", "untested", 0, now_iso, now_iso),
                    (str(uuid.uuid4()), "smartrecruiters", "Visa", "visa", "untested", 0, now_iso, now_iso),
                    (str(uuid.uuid4()), "smartrecruiters", "McDonalds", "mcdonalds", "untested", 0, now_iso, now_iso),
                    (str(uuid.uuid4()), "jobicy", "Jobicy Remote", "jobicy", "untested", 0, now_iso, now_iso),
                    (str(uuid.uuid4()), "manual", "Direct Import", "manual", "verified_active", 0, now_iso, now_iso),
                ]
                for row in default_sources:
                    conn.exec_driver_sql(
                        "INSERT INTO job_sources (id, provider, employer_name, board_identifier, status, last_job_count, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        row,
                    )
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
