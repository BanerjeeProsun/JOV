"""Application Service for atomic state transitions and optimistic locking."""

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from jovsi.domain.state_machine import (
    ApplicationState,
    IllegalTransition,
    GuardFailure,
    StateMachine,
    TransitionContext,
)
from jovsi.adapters.db.models import ApplicationDB, EventDB


class VersionConflict(Exception):
    """Raised when an application row version does not match the expected version."""

    def __init__(self, app_id: str, current_version: int, expected_version: int):
        self.app_id = app_id
        self.current_version = current_version
        self.expected_version = expected_version
        super().__init__(
            f"Version conflict for application {app_id}: expected {expected_version}, found {current_version}"
        )


class ApplicationNotFound(Exception):
    pass


class ApplicationService:
    @classmethod
    def transition(
        cls,
        db: Session,
        app_id: str,
        to_state: ApplicationState,
        trigger: str,
        expected_version: int,
        actor: str = "system",
        payload: Optional[Dict[str, Any]] = None,
        ctx: Optional[TransitionContext] = None,
    ) -> ApplicationDB:
        """Execute a state machine transition inside an atomic transaction.

        Guarantees:
        1. Checks optimistic version lock.
        2. Pure domain state machine validates legal transition and guard.
        3. Updates application state and increments version.
        4. Appends audit event.
        """
        app = db.scalar(select(ApplicationDB).where(ApplicationDB.id == app_id))
        if not app:
            raise ApplicationNotFound(f"Application {app_id} not found")

        if app.version != expected_version:
            raise VersionConflict(app_id, app.version, expected_version)

        from_state = ApplicationState(app.state)

        # Build context if not provided
        if ctx is None:
            ctx = TransitionContext(
                application_id=app.id,
                current_state=from_state,
                target_state=to_state,
                canonical_job_key=app.canonical_job_key,
            )
        else:
            ctx.current_state = from_state
            ctx.target_state = to_state

        # Validate through pure domain state machine
        StateMachine.validate_transition(ctx)

        # Update application state
        app.state = to_state.value
        app.version += 1

        if to_state == ApplicationState.PAUSED_AUTH:
            app.paused_from_state = from_state.value
        elif from_state == ApplicationState.PAUSED_AUTH:
            app.paused_from_state = None

        # Append audit event
        event_row = EventDB(
            application_id=app.id,
            type=trigger,
            from_state=from_state.value,
            to_state=to_state.value,
            actor=actor,
            payload=payload or {},
        )
        db.add(event_row)
        db.commit()
        db.refresh(app)
        return app
