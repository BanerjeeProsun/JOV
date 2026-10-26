"""Unit tests for Fact Provenance Engine (Blueprint v2.0 Section 6)."""

from datetime import date
import pytest
from jovsi.domain.models import FactKind, FactProvenance, FactStatus
from jovsi.domain.provenance import ProvenanceEngine, ProvenanceError


def test_create_user_fact() -> None:
    fact = ProvenanceEngine.create_user_fact(
        candidate_id="cand-1",
        kind=FactKind.SKILL,
        key="python",
        value={"name": "Python", "years": 5},
    )
    assert fact.status == FactStatus.ACTIVE
    assert fact.provenance == FactProvenance.USER_SUPPLIED
    assert fact.is_usable is True


def test_propose_and_confirm_fact() -> None:
    proposed = ProvenanceEngine.propose_extracted_fact(
        candidate_id="cand-1",
        kind=FactKind.EDUCATION,
        key="degree",
        value={"degree_level": "BACHELOR", "field": "Computer Science"},
        source_document_id="doc-123",
    )
    assert proposed.status == FactStatus.PROPOSED
    assert proposed.is_usable is False

    confirmed = ProvenanceEngine.confirm_proposed_fact(proposed)
    assert confirmed.status == FactStatus.ACTIVE
    assert confirmed.provenance == FactProvenance.USER_VERIFIED
    assert confirmed.is_usable is True
    assert confirmed.verified_at is not None


def test_reject_proposed_fact() -> None:
    proposed = ProvenanceEngine.propose_extracted_fact(
        candidate_id="cand-1",
        kind=FactKind.SKILL,
        key="unverified_skill",
        value={"name": "Fortran"},
        source_document_id="doc-123",
    )
    rejected = ProvenanceEngine.reject_proposed_fact(proposed)
    assert rejected.status == FactStatus.REJECTED
    assert rejected.is_usable is False


def test_supersede_fact() -> None:
    old_fact = ProvenanceEngine.create_user_fact(
        candidate_id="cand-1",
        kind=FactKind.CONTACT,
        key="phone",
        value={"number": "+1234567890"},
    )
    assert old_fact.status == FactStatus.ACTIVE

    archived_old, new_fact = ProvenanceEngine.supersede_fact(
        old_fact=old_fact,
        new_key="phone",
        new_value={"number": "+1987654321"},
    )
    assert archived_old.status == FactStatus.SUPERSEDED
    assert archived_old.is_usable is False

    assert new_fact.status == FactStatus.ACTIVE
    assert new_fact.is_usable is True
    assert new_fact.supersedes_id == old_fact.id
