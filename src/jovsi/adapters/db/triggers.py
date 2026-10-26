"""Database triggers for append-only audit event enforcement (Invariant 12)."""

from sqlalchemy import Connection, text


SQLITE_EVENT_TRIGGER_NO_UPDATE = """
CREATE TRIGGER IF NOT EXISTS prevent_events_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'Audit events are append-only: UPDATE is prohibited');
END;
"""

SQLITE_EVENT_TRIGGER_NO_DELETE = """
CREATE TRIGGER IF NOT EXISTS prevent_events_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'Audit events are append-only: DELETE is prohibited');
END;
"""


def apply_immutability_triggers(connection: Connection) -> None:
    """Apply SQLite triggers to reject UPDATE and DELETE operations on the events table."""
    dialect_name = connection.dialect.name
    if dialect_name == "sqlite":
        connection.execute(text(SQLITE_EVENT_TRIGGER_NO_UPDATE))
        connection.execute(text(SQLITE_EVENT_TRIGGER_NO_DELETE))
