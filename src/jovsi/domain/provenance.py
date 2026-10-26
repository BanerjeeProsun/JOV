"""JOV.si Fact Provenance and Verification Engine.

Enforces Blueprint v2.0 Section 6 rules:
- Facts: ACTIVE, PROPOSED, REJECTED, SUPERSEDED
- Provenance: USER_SUPPLIED, USER_VERIFIED
- Only ACTIVE facts with USER_SUPPLIED or USER_VERIFIED may be used in output.
- Derivations (deterministic formulas over active facts) are allowed with DERIVED label.
- Inferences (unsupported extrapolations) are strictly blocked.
"""

from datetime import datetime, date
from typing import Any, Dict, List, Optional
from jovsi.domain.models import Fact, FactKind, FactProvenance, FactStatus


class ProvenanceError(Exception):
    pass


class ProvenanceEngine:
    @classmethod
    def create_user_fact(
        cls,
        candidate_id: str,
        kind: FactKind,
        key: str,
        value: Dict[str, Any],
        source_document_id: Optional[str] = None,
        valid_from: Optional[date] = None,
        valid_to: Optional[date] = None,
    ) -> Fact:
        """Create a fact directly supplied by the user (status=ACTIVE, provenance=USER_SUPPLIED)."""
        import uuid
        return Fact(
            id=str(uuid.uuid4()),
            candidate_id=candidate_id,
            kind=kind,
            key=key,
            value=value,
            provenance=FactProvenance.USER_SUPPLIED,
            status=FactStatus.ACTIVE,
            source_document_id=source_document_id,
            verified_at=datetime.utcnow(),
            valid_from=valid_from,
            valid_to=valid_to,
        )

    @classmethod
    def propose_extracted_fact(
        cls,
        candidate_id: str,
        kind: FactKind,
        key: str,
        value: Dict[str, Any],
        source_document_id: str,
    ) -> Fact:
        """Create a fact proposed by extraction (status=PROPOSED, NOT usable in output until confirmed)."""
        import uuid
        return Fact(
            id=str(uuid.uuid4()),
            candidate_id=candidate_id,
            kind=kind,
            key=key,
            value=value,
            provenance=FactProvenance.USER_VERIFIED,
            status=FactStatus.PROPOSED,
            source_document_id=source_document_id,
        )

    @classmethod
    def confirm_proposed_fact(cls, fact: Fact) -> Fact:
        """User explicitly confirms a proposed fact, making it ACTIVE and usable."""
        if fact.status != FactStatus.PROPOSED:
            raise ProvenanceError(f"Cannot confirm fact in status {fact.status}")
        
        return fact.model_copy(
            update={
                "status": FactStatus.ACTIVE,
                "provenance": FactProvenance.USER_VERIFIED,
                "verified_at": datetime.utcnow(),
            }
        )

    @classmethod
    def reject_proposed_fact(cls, fact: Fact) -> Fact:
        """User explicitly rejects a proposed fact."""
        return fact.model_copy(update={"status": FactStatus.REJECTED})

    @classmethod
    def supersede_fact(
        cls,
        old_fact: Fact,
        new_key: str,
        new_value: Dict[str, Any],
        provenance: FactProvenance = FactProvenance.USER_SUPPLIED,
    ) -> tuple[Fact, Fact]:
        """Supersede an older fact without mutating history."""
        import uuid
        updated_old = old_fact.model_copy(update={"status": FactStatus.SUPERSEDED})
        new_fact = Fact(
            id=str(uuid.uuid4()),
            candidate_id=old_fact.candidate_id,
            kind=old_fact.kind,
            key=new_key,
            value=new_value,
            provenance=provenance,
            status=FactStatus.ACTIVE,
            supersedes_id=old_fact.id,
            verified_at=datetime.utcnow(),
        )
        return updated_old, new_fact
