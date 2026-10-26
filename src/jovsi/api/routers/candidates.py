"""Candidate and Fact Management API Routers."""

from datetime import datetime
import hashlib
import os
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from jovsi.adapters.db.session import get_db
from jovsi.adapters.db.models import CandidateDB, DocumentDB, FactDB
from jovsi.api.schemas import (
    CandidateCreate,
    CandidateResponse,
    FactCreate,
    FactResponse,
    FactUpdate,
    MasterResumeResponse,
    MasterResumeStatusResponse,
)
from jovsi.domain.models import FactKind, FactProvenance, FactStatus
from jovsi.domain.provenance import ProvenanceEngine
from jovsi.services.resume_parser import MasterResumeParser, ResumeParsingError



router = APIRouter(tags=["Candidates & Facts"])


@router.post("/candidates", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def create_candidate(data: CandidateCreate, db: Session = Depends(get_db)) -> CandidateResponse:
    candidate = CandidateDB(
        display_name=data.display_name,
        timezone=data.timezone,
        is_synthetic=data.is_synthetic,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return CandidateResponse(
        id=candidate.id,
        display_name=candidate.display_name,
        timezone=candidate.timezone,
        is_synthetic=candidate.is_synthetic,
        created_at=candidate.created_at,
    )


@router.get("/candidates", response_model=List[CandidateResponse])
def list_candidates(db: Session = Depends(get_db)) -> List[CandidateResponse]:
    candidates = db.scalars(select(CandidateDB).order_by(CandidateDB.created_at.asc())).all()
    return [
        CandidateResponse(
            id=c.id,
            display_name=c.display_name,
            timezone=c.timezone,
            is_synthetic=c.is_synthetic,
            created_at=c.created_at,
        )
        for c in candidates
    ]


@router.get("/candidates/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: str, db: Session = Depends(get_db)) -> CandidateResponse:
    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == candidate_id))
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return CandidateResponse(
        id=candidate.id,
        display_name=candidate.display_name,
        timezone=candidate.timezone,
        is_synthetic=candidate.is_synthetic,
        created_at=candidate.created_at,
    )


@router.get("/candidates/{candidate_id}/facts", response_model=List[FactResponse])
def list_candidate_facts(candidate_id: str, db: Session = Depends(get_db)) -> List[FactResponse]:
    facts = db.scalars(select(FactDB).where(FactDB.candidate_id == candidate_id)).all()
    return [
        FactResponse(
            id=f.id,
            candidate_id=f.candidate_id,
            kind=FactKind(f.kind),
            key=f.key,
            value=f.value,
            provenance=FactProvenance(f.provenance),
            status=FactStatus(f.status),
            source_document_id=f.source_document_id,
            verified_at=f.verified_at,
            valid_from=f.valid_from,
            valid_to=f.valid_to,
            is_usable=(f.status == "ACTIVE" and f.provenance in ("USER_SUPPLIED", "USER_VERIFIED")),
        )
        for f in facts
    ]


@router.post("/candidates/{candidate_id}/facts", response_model=FactResponse, status_code=status.HTTP_201_CREATED)
def add_candidate_fact(candidate_id: str, data: FactCreate, db: Session = Depends(get_db)) -> FactResponse:
    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == candidate_id))
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    domain_fact = ProvenanceEngine.create_user_fact(
        candidate_id=candidate_id,
        kind=data.kind,
        key=data.key,
        value=data.value,
        source_document_id=data.source_document_id,
        valid_from=data.valid_from,
        valid_to=data.valid_to,
    )

    db_fact = FactDB(
        id=domain_fact.id,
        candidate_id=domain_fact.candidate_id,
        kind=domain_fact.kind.value,
        key=domain_fact.key,
        value=domain_fact.value,
        provenance=domain_fact.provenance.value,
        status=domain_fact.status.value,
        source_document_id=domain_fact.source_document_id,
        verified_at=domain_fact.verified_at,
        valid_from=domain_fact.valid_from,
        valid_to=domain_fact.valid_to,
    )
    db.add(db_fact)
    db.commit()
    db.refresh(db_fact)

    return FactResponse(
        id=db_fact.id,
        candidate_id=db_fact.candidate_id,
        kind=FactKind(db_fact.kind),
        key=db_fact.key,
        value=db_fact.value,
        provenance=FactProvenance(db_fact.provenance),
        status=FactStatus(db_fact.status),
        source_document_id=db_fact.source_document_id,
        verified_at=db_fact.verified_at,
        valid_from=db_fact.valid_from,
        valid_to=db_fact.valid_to,
        is_usable=domain_fact.is_usable,
    )


@router.post("/facts/{fact_id}/confirm", response_model=FactResponse)
def confirm_fact(fact_id: str, db: Session = Depends(get_db)) -> FactResponse:
    fact = db.scalar(select(FactDB).where(FactDB.id == fact_id))
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    fact.status = FactStatus.ACTIVE.value
    fact.provenance = FactProvenance.USER_VERIFIED.value
    from datetime import datetime
    fact.verified_at = datetime.utcnow()
    db.commit()
    db.refresh(fact)

    return FactResponse(
        id=fact.id,
        candidate_id=fact.candidate_id,
        kind=FactKind(fact.kind),
        key=fact.key,
        value=fact.value,
        provenance=FactProvenance(fact.provenance),
        status=FactStatus(fact.status),
        source_document_id=fact.source_document_id,
        verified_at=fact.verified_at,
        valid_from=fact.valid_from,
        valid_to=fact.valid_to,
        is_usable=True,
    )


@router.post("/facts/{fact_id}/reject", response_model=FactResponse)
def reject_fact(fact_id: str, db: Session = Depends(get_db)) -> FactResponse:
    fact = db.scalar(select(FactDB).where(FactDB.id == fact_id))
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    fact.status = FactStatus.REJECTED.value
    db.commit()
    db.refresh(fact)

    return FactResponse(
        id=fact.id,
        candidate_id=fact.candidate_id,
        kind=FactKind(fact.kind),
        key=fact.key,
        value=fact.value,
        provenance=FactProvenance(fact.provenance),
        status=FactStatus(fact.status),
        source_document_id=fact.source_document_id,
        verified_at=fact.verified_at,
        valid_from=fact.valid_from,
        valid_to=fact.valid_to,
        is_usable=False,
    )


@router.put("/facts/{fact_id}", response_model=FactResponse)
def update_fact(fact_id: str, data: FactUpdate, db: Session = Depends(get_db)) -> FactResponse:
    fact = db.scalar(select(FactDB).where(FactDB.id == fact_id))
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")

    if data.key:
        fact.key = data.key
    fact.value = data.value
    db.commit()
    db.refresh(fact)

    return FactResponse(
        id=fact.id,
        candidate_id=fact.candidate_id,
        kind=FactKind(fact.kind),
        key=fact.key,
        value=fact.value,
        provenance=FactProvenance(fact.provenance),
        status=FactStatus(fact.status),
        source_document_id=fact.source_document_id,
        verified_at=fact.verified_at,
        valid_from=fact.valid_from,
        valid_to=fact.valid_to,
        is_usable=(fact.status == "ACTIVE" and fact.provenance in ("USER_SUPPLIED", "USER_VERIFIED")),
    )


@router.delete("/facts/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fact(fact_id: str, db: Session = Depends(get_db)):
    fact = db.scalar(select(FactDB).where(FactDB.id == fact_id))
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    db.delete(fact)
    db.commit()


@router.post("/candidates/{candidate_id}/confirm-all-facts", response_model=List[FactResponse])
def confirm_all_facts(candidate_id: str, db: Session = Depends(get_db)) -> List[FactResponse]:
    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == candidate_id))
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    proposed_facts = db.scalars(
        select(FactDB).where(FactDB.candidate_id == candidate_id, FactDB.status == FactStatus.PROPOSED.value)
    ).all()

    now = datetime.utcnow()
    for f in proposed_facts:
        f.status = FactStatus.ACTIVE.value
        f.provenance = FactProvenance.USER_VERIFIED.value
        f.verified_at = now

    db.commit()

    all_facts = db.scalars(select(FactDB).where(FactDB.candidate_id == candidate_id)).all()
    return [
        FactResponse(
            id=f.id,
            candidate_id=f.candidate_id,
            kind=FactKind(f.kind),
            key=f.key,
            value=f.value,
            provenance=FactProvenance(f.provenance),
            status=FactStatus(f.status),
            source_document_id=f.source_document_id,
            verified_at=f.verified_at,
            valid_from=f.valid_from,
            valid_to=f.valid_to,
            is_usable=(f.status == "ACTIVE" and f.provenance in ("USER_SUPPLIED", "USER_VERIFIED")),
        )
        for f in all_facts
    ]


@router.get("/candidates/{candidate_id}/master-resume", response_model=MasterResumeStatusResponse)
def get_master_resume_status(candidate_id: str, db: Session = Depends(get_db)) -> MasterResumeStatusResponse:
    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == candidate_id))
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    doc = db.scalar(
        select(DocumentDB)
        .where(DocumentDB.candidate_id == candidate_id, DocumentDB.kind == "MASTER_RESUME")
        .order_by(DocumentDB.created_at.desc())
    )

    facts = db.scalars(select(FactDB).where(FactDB.candidate_id == candidate_id)).all()
    total_facts = len(facts)
    active_facts = sum(1 for f in facts if f.status == "ACTIVE")
    proposed_facts = sum(1 for f in facts if f.status == "PROPOSED")

    if not doc:
        return MasterResumeStatusResponse(
            has_master_resume=False,
            total_facts=total_facts,
            active_facts=active_facts,
            proposed_facts=proposed_facts,
        )

    filename = os.path.basename(doc.path).split("_", 1)[-1]
    return MasterResumeStatusResponse(
        has_master_resume=True,
        document_id=doc.id,
        filename=filename,
        sha256=doc.sha256,
        uploaded_at=doc.created_at,
        total_facts=total_facts,
        active_facts=active_facts,
        proposed_facts=proposed_facts,
    )


@router.post("/candidates/{candidate_id}/resume/upload", response_model=MasterResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_master_resume(
    candidate_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> MasterResumeResponse:
    candidate = db.scalar(select(CandidateDB).where(CandidateDB.id == candidate_id))
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    filename = file.filename or "resume.pdf"
    content = await file.read()

    try:
        raw_text = MasterResumeParser.extract_text_from_bytes(content, filename)
    except ResumeParsingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected parsing error: {e}")

    # Compute SHA-256
    file_sha256 = hashlib.sha256(content).hexdigest()

    # Store file to disk safely
    storage_dir = Path("storage") / "documents" / candidate_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    saved_filename = f"{file_sha256[:16]}_{filename}"
    file_path = storage_dir / saved_filename
    file_path.write_bytes(content)

    # Save or update Master Document record
    # If a document with same sha256 already exists for this candidate, use it; otherwise create
    doc = db.scalar(
        select(DocumentDB).where(DocumentDB.candidate_id == candidate_id, DocumentDB.sha256 == file_sha256)
    )
    if not doc:
        doc = DocumentDB(
            candidate_id=candidate_id,
            kind="MASTER_RESUME",
            sha256=file_sha256,
            path=str(file_path),
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
    else:
        doc.kind = "MASTER_RESUME"
        doc.path = str(file_path)
        db.commit()

    # Extract structured entities
    entities = MasterResumeParser.extract_structured_entities(raw_text)

    # Update candidate display_name if candidate name was extracted and not already set
    extracted_name = entities.get("name")
    if extracted_name and extracted_name != "Candidate" and (candidate.display_name in ("Candidate", "Ada Lovelace", "")):
        candidate.display_name = extracted_name
        db.commit()

    # Generate proposed facts
    proposed_fact_dicts = MasterResumeParser.build_proposed_facts(candidate_id, doc.id, entities)

    created_facts: List[FactResponse] = []
    for f_dict in proposed_fact_dicts:
        # Check if identical fact key already exists to prevent unnecessary duplicates
        existing = db.scalar(
            select(FactDB).where(FactDB.candidate_id == candidate_id, FactDB.key == f_dict["key"])
        )
        if existing:
            existing.value = f_dict["value"]
            existing.source_document_id = doc.id
            existing.status = FactStatus.PROPOSED.value
            db.commit()
            db.refresh(existing)
            created_facts.append(
                FactResponse(
                    id=existing.id,
                    candidate_id=existing.candidate_id,
                    kind=FactKind(existing.kind),
                    key=existing.key,
                    value=existing.value,
                    provenance=FactProvenance(existing.provenance),
                    status=FactStatus(existing.status),
                    source_document_id=existing.source_document_id,
                    verified_at=existing.verified_at,
                    valid_from=existing.valid_from,
                    valid_to=existing.valid_to,
                    is_usable=False,
                )
            )
        else:
            db_fact = FactDB(
                candidate_id=candidate_id,
                kind=f_dict["kind"],
                key=f_dict["key"],
                value=f_dict["value"],
                provenance=f_dict["provenance"],
                status=f_dict["status"],
                source_document_id=doc.id,
            )
            db.add(db_fact)
            db.commit()
            db.refresh(db_fact)
            created_facts.append(
                FactResponse(
                    id=db_fact.id,
                    candidate_id=db_fact.candidate_id,
                    kind=FactKind(db_fact.kind),
                    key=db_fact.key,
                    value=db_fact.value,
                    provenance=FactProvenance(db_fact.provenance),
                    status=FactStatus(db_fact.status),
                    source_document_id=db_fact.source_document_id,
                    verified_at=db_fact.verified_at,
                    valid_from=db_fact.valid_from,
                    valid_to=db_fact.valid_to,
                    is_usable=False,
                )
            )

    return MasterResumeResponse(
        document_id=doc.id,
        candidate_id=candidate_id,
        filename=filename,
        sha256=file_sha256,
        uploaded_at=doc.created_at,
        entities=entities,
        total_facts_extracted=len(created_facts),
        proposed_facts=created_facts,
    )


@router.get("/documents/{document_id}/download")
def download_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.scalar(select(DocumentDB).where(DocumentDB.id == document_id))
    if not doc or not os.path.exists(doc.path):
        raise HTTPException(status_code=404, detail="Document file not found on disk")

    filename = os.path.basename(doc.path).split("_", 1)[-1]
    return FileResponse(path=doc.path, filename=filename, media_type="application/octet-stream")


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.scalar(select(DocumentDB).where(DocumentDB.id == document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if os.path.exists(doc.path):
        try:
            os.remove(doc.path)
        except OSError:
            pass

    db.delete(doc)
    db.commit()

