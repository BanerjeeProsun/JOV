"""JOV.si External Portal Authentication & Session Management.

Provides:
- Detection and lifecycle management for portals requiring candidate authentication
- State transition to PAUSED_AUTH preserving previous application state
- Anti-tamper re-inspection upon login resolution (form skeleton hash verification)
- Resumption back to preserved pre-submission state
- Secure encryption helper for sensitive portal tokens/credentials
"""

from datetime import datetime
import hashlib
import json
import logging
from typing import Any, Dict, Optional, Tuple
from cryptography.fernet import Fernet
import base64

from sqlalchemy.orm import Session
from sqlalchemy import select

from jovsi.config import settings
from jovsi.domain.state_machine import ApplicationState, StateMachine, TransitionContext
from jovsi.adapters.db.models import ApplicationDB, EventDB, FormSnapshotDB, JobDB

logger = logging.getLogger(__name__)


class PortalAuthService:
    @classmethod
    def get_cipher(cls, salt: str = "jovsi_portal_vault") -> Fernet:
        """Derive safe Fernet cipher from application SECRET_KEY."""
        raw_key = hashlib.sha256(f"{settings.SECRET_KEY}:{salt}".encode("utf-8")).digest()
        b64_key = base64.urlsafe_b64encode(raw_key)
        return Fernet(b64_key)

    @classmethod
    def encrypt_secret(cls, plaintext: str, salt: str = "jovsi_portal_vault") -> str:
        cipher = cls.get_cipher(salt)
        return cipher.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    @classmethod
    def decrypt_secret(cls, ciphertext: str, salt: str = "jovsi_portal_vault") -> str:
        cipher = cls.get_cipher(salt)
        return cipher.decrypt(ciphertext.encode("utf-8")).decode("utf-8")

    @classmethod
    def pause_for_authentication(
        cls,
        db: Session,
        application_id: str,
        reason: str = "Portal requires candidate authentication (SSO/2FA/password)",
        actor: str = "system",
    ) -> ApplicationDB:
        """Transitions application into PAUSED_AUTH while preserving previous state."""
        app = db.scalar(select(ApplicationDB).where(ApplicationDB.id == application_id))
        if not app:
            raise ValueError(f"Application {application_id} not found")

        current_state = ApplicationState(app.state)
        ctx = TransitionContext(
            application_id=app.id,
            current_state=current_state,
            target_state=ApplicationState.PAUSED_AUTH,
        )
        StateMachine.validate_transition(ctx)

        app.paused_from_state = current_state.value
        app.state = ApplicationState.PAUSED_AUTH.value
        app.version += 1

        event = EventDB(
            application_id=app.id,
            type="PORTAL_AUTH_REQUIRED",
            from_state=current_state.value,
            to_state=ApplicationState.PAUSED_AUTH.value,
            actor=actor,
            payload={"reason": reason},
        )
        db.add(event)
        db.commit()
        db.refresh(app)
        return app

    @classmethod
    def resume_from_authentication(
        cls,
        db: Session,
        application_id: str,
        new_skeleton_hash: Optional[str] = None,
        actor: str = "candidate",
    ) -> Tuple[ApplicationDB, bool]:
        """Resumes an application from PAUSED_AUTH back to its saved pre-submission state.
        
        Performs anti-tamper verification against earlier FormSnapshotDB if available.
        """
        app = db.scalar(select(ApplicationDB).where(ApplicationDB.id == application_id))
        if not app:
            raise ValueError(f"Application {application_id} not found")

        if app.state != ApplicationState.PAUSED_AUTH.value:
            raise ValueError(f"Application is not in PAUSED_AUTH (current state: {app.state})")

        return_state_name = app.paused_from_state or ApplicationState.READY_FOR_REVIEW.value
        target_state = ApplicationState(return_state_name)

        # Anti-tamper verification
        snapshot = db.scalar(
            select(FormSnapshotDB)
            .where(FormSnapshotDB.application_id == application_id)
            .order_by(FormSnapshotDB.created_at.desc())
        )
        tamper_verified = True
        if snapshot and new_skeleton_hash:
            if snapshot.dom_hash != new_skeleton_hash:
                tamper_verified = False
                logger.warning(
                    "Form skeleton drift detected on resume: original %s != new %s",
                    snapshot.dom_hash,
                    new_skeleton_hash,
                )

        ctx = TransitionContext(
            application_id=app.id,
            current_state=ApplicationState.PAUSED_AUTH,
            target_state=target_state,
        )
        StateMachine.validate_transition(ctx)

        app.state = target_state.value
        app.paused_from_state = None
        app.version += 1

        event = EventDB(
            application_id=app.id,
            type="PORTAL_AUTH_RESOLVED",
            from_state=ApplicationState.PAUSED_AUTH.value,
            to_state=target_state.value,
            actor=actor,
            payload={"tamper_verified": tamper_verified},
        )
        db.add(event)
        db.commit()
        db.refresh(app)
        return app, tamper_verified
