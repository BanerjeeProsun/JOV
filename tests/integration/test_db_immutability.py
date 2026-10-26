"""Integration test for SQLite append-only audit log triggers (Invariant 12)."""

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError

from jovsi.adapters.db.models import Base, EventDB
from jovsi.adapters.db.session import init_db


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        yield session


def test_events_insert_succeeds(test_db: Session) -> None:
    event = EventDB(
        application_id="app-test",
        type="TEST_TRIGGER",
        from_state="DISCOVERED",
        to_state="ELIGIBILITY_CHECKED",
        actor="test_runner",
        payload={"note": "valid audit record"},
    )
    test_db.add(event)
    test_db.commit()

    saved = test_db.scalar(select(EventDB).where(EventDB.application_id == "app-test"))
    assert saved is not None
    assert saved.to_state == "ELIGIBILITY_CHECKED"


def test_events_update_fails_due_to_trigger(test_db: Session) -> None:
    event = EventDB(
        application_id="app-test-update",
        type="TEST_TRIGGER",
        from_state="DISCOVERED",
        to_state="ELIGIBILITY_CHECKED",
        actor="test_runner",
    )
    test_db.add(event)
    test_db.commit()

    # Attempt to update the event row directly
    event.to_state = "SHORTLISTED"
    with pytest.raises(DBAPIError) as exc_info:
        test_db.commit()
    
    assert "Audit events are append-only: UPDATE is prohibited" in str(exc_info.value)
    test_db.rollback()


def test_events_delete_fails_due_to_trigger(test_db: Session) -> None:
    event = EventDB(
        application_id="app-test-delete",
        type="TEST_TRIGGER",
        from_state="DISCOVERED",
        to_state="ELIGIBILITY_CHECKED",
        actor="test_runner",
    )
    test_db.add(event)
    test_db.commit()

    # Attempt to delete the event row directly
    test_db.delete(event)
    with pytest.raises(DBAPIError) as exc_info:
        test_db.commit()

    assert "Audit events are append-only: DELETE is prohibited" in str(exc_info.value)
    test_db.rollback()
