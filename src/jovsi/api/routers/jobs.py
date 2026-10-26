"""Job Ingestion and Discovery API Router."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from jovsi.adapters.db.session import get_db
from jovsi.adapters.db.models import CandidateDB, FactDB, JobDB
from jovsi.adapters.sanitizer import UntrustedInputSanitizer
from jovsi.api.schemas import JobImportRequest, JobResponse
from jovsi.domain.models import DegreeLevel, Fact, FactKind, FactProvenance, FactStatus, Job, JobRequirements, JobStatus
from jovsi.services.job_discovery import JobDiscoveryService



router = APIRouter(tags=["Jobs"])


@router.post("/jobs/import", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def import_job(data: JobImportRequest, db: Session = Depends(get_db)) -> JobResponse:
    # 1. Sanitize raw description (strips hidden divs, scripts, zero-width chars)
    raw_sha256, cleaned_desc = UntrustedInputSanitizer.sanitize(data.raw_description)

    # 2. Normalize company, title, and calculate canonical key
    company_norm = data.company_name.strip()
    title_norm = data.title.strip()
    canonical_key = Job.compute_canonical_key(
        company_norm=company_norm,
        title_norm=title_norm,
        portal_key=data.portal_key,
        native_id=data.native_id,
    )

    # 3. Check for existing identical job
    existing = db.scalar(
        select(JobDB).where(
            JobDB.source == data.source,
            JobDB.canonical_job_key == canonical_key,
        )
    )
    if existing:
        return JobResponse(
            id=existing.id,
            source=existing.source,
            source_url=existing.source_url,
            canonical_url=existing.canonical_url,
            canonical_job_key=existing.canonical_job_key,
            company_norm=existing.company_norm,
            title_norm=existing.title_norm,
            description_clean=existing.description_clean,
            raw_sha256=existing.raw_sha256,
            requirements=existing.requirements,
            deadline_at=existing.deadline_at,
            status=JobStatus(existing.status),
            created_at=existing.created_at,
        )

    requirements = JobRequirements(
        min_degree=data.min_degree,
        allowed_graduation_years=data.allowed_graduation_years,
        min_experience_months=data.min_experience_months,
        work_auth_countries=data.work_auth_countries,
        mandatory_certifications=data.mandatory_certifications,
        required_skills=data.required_skills,
        preferred_skills=data.preferred_skills,
        responsibilities=data.responsibilities,
        accepted_work_modes=data.accepted_work_modes,
        target_locations=data.target_locations,
        deadline=data.deadline_at,
    )

    db_job = JobDB(
        source=data.source,
        source_url=data.source_url,
        canonical_url=data.canonical_url or data.source_url,
        canonical_job_key=canonical_key,
        company_norm=company_norm,
        title_norm=title_norm,
        description_clean=cleaned_desc,
        raw_sha256=raw_sha256,
        requirements=requirements.model_dump(),
        deadline_at=data.deadline_at,
        status=JobStatus.ACTIVE.value,
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)

    return JobResponse(
        id=db_job.id,
        source=db_job.source,
        source_url=db_job.source_url,
        canonical_url=db_job.canonical_url,
        canonical_job_key=db_job.canonical_job_key,
        company_norm=db_job.company_norm,
        title_norm=db_job.title_norm,
        description_clean=db_job.description_clean,
        raw_sha256=db_job.raw_sha256,
        requirements=db_job.requirements,
        deadline_at=db_job.deadline_at,
        status=JobStatus(db_job.status),
        created_at=db_job.created_at,
    )


@router.get("/jobs", response_model=List[JobResponse])
def list_jobs(
    status: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[JobResponse]:
    stmt = select(JobDB)
    if status:
        stmt = stmt.where(JobDB.status == status)
    if company:
        stmt = stmt.where(JobDB.company_norm.ilike(f"%{company}%"))
    stmt = stmt.order_by(JobDB.created_at.desc()).limit(limit)

    jobs = db.scalars(stmt).all()
    return [
        JobResponse(
            id=j.id,
            source=j.source,
            source_url=j.source_url,
            canonical_url=j.canonical_url,
            canonical_job_key=j.canonical_job_key,
            company_norm=j.company_norm,
            title_norm=j.title_norm,
            description_clean=j.description_clean,
            raw_sha256=j.raw_sha256,
            requirements=j.requirements,
            deadline_at=j.deadline_at,
            status=JobStatus(j.status),
            created_at=j.created_at,
        )
        for j in jobs
    ]


class DiscoverJobsRequest(BaseModel):
    source: str = "all"
    query: str = ""
    company: Optional[str] = None
    location: Optional[str] = None
    limit: int = 20
    candidate_id: Optional[str] = None


class DiscoveredJobItem(BaseModel):
    id: str
    source: str
    source_url: str
    canonical_url: str
    company_name: str
    title: str
    location: str
    description: str
    required_skills: List[str]
    match_score: Optional[float] = None
    rules_result: Optional[str] = None
    rules_reason: Optional[str] = None
    matched_skills: List[str] = []
    missing_skills: List[str] = []


class DiscoverJobsResponse(BaseModel):
    total_found: int
    source_status: Dict[str, str]
    jobs: List[DiscoveredJobItem]


@router.get("/jobs/sources", response_model=List[Dict[str, Any]])
def get_job_sources() -> List[Dict[str, Any]]:
    return JobDiscoveryService.get_registered_sources()


@router.post("/jobs/discover", response_model=DiscoverJobsResponse)
def discover_jobs(
    data: DiscoverJobsRequest,
    db: Session = Depends(get_db),
) -> DiscoverJobsResponse:
    # 1. Fetch from real external APIs
    raw_results, status_map = JobDiscoveryService.discover_jobs(
        source=data.source,
        query=data.query,
        company=data.company,
        location=data.location,
        limit=data.limit,
    )

    # 2. Fetch candidate facts if candidate_id provided
    candidate_facts: List[Fact] = []
    if data.candidate_id:
        fact_rows = db.scalars(select(FactDB).where(FactDB.candidate_id == data.candidate_id)).all()
        candidate_facts = [
            Fact(
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
            )
            for f in fact_rows
        ]

    # 3. Store and optionally rank each discovered job
    output_items: List[DiscoveredJobItem] = []
    for item in raw_results:
        # Sanitize description
        raw_sha256, cleaned_desc = UntrustedInputSanitizer.sanitize(item["raw_description"])
        comp_norm = item["company_name"].strip()
        title_norm = item["title"].strip()
        canonical_key = Job.compute_canonical_key(
            company_norm=comp_norm,
            title_norm=title_norm,
            portal_key=item.get("portal_key"),
            native_id=item.get("native_id"),
        )

        # Check existing or create in db
        existing = db.scalar(
            select(JobDB).where(
                JobDB.source == item["source"],
                JobDB.canonical_job_key == canonical_key,
            )
        )
        if not existing:
            reqs = JobRequirements(
                min_degree=DegreeLevel.BACHELOR,
                min_experience_months=24,
                required_skills=item.get("required_skills", []),
                work_auth_countries=["US", "UK", "IN"],
                accepted_work_modes=item.get("accepted_work_modes", ["remote", "hybrid", "onsite"]),
            )
            existing = JobDB(
                source=item["source"],
                source_url=item["source_url"],
                canonical_url=item["source_url"],
                canonical_job_key=canonical_key,
                company_norm=comp_norm,
                title_norm=title_norm,
                description_clean=cleaned_desc,
                raw_sha256=raw_sha256,
                requirements=reqs.model_dump(),
                status=JobStatus.ACTIVE.value,
            )
            db.add(existing)
            db.commit()
            db.refresh(existing)

        # Rank against candidate facts
        ranking_info: Dict[str, Any] = {}
        if candidate_facts:
            ranking_info = JobDiscoveryService.rank_job_for_candidate(item, candidate_facts)

        output_items.append(
            DiscoveredJobItem(
                id=existing.id,
                source=existing.source,
                source_url=existing.source_url,
                canonical_url=existing.canonical_url,
                company_name=comp_norm,
                title=title_norm,
                location=item.get("location", "Remote / Flexible"),
                description=cleaned_desc[:500],
                required_skills=item.get("required_skills", []),
                match_score=ranking_info.get("score_total"),
                rules_result=ranking_info.get("rules_result"),
                rules_reason=ranking_info.get("rules_reason"),
                matched_skills=ranking_info.get("matched_skills", []),
                missing_skills=ranking_info.get("missing_skills", []),
            )
        )

    # Sort by match score descending if ranked
    if candidate_facts:
        output_items.sort(key=lambda x: (x.match_score or 0.0), reverse=True)

    return DiscoverJobsResponse(
        total_found=len(output_items),
        source_status=status_map,
        jobs=output_items,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    job = db.scalar(select(JobDB).where(JobDB.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse(
        id=job.id,
        source=job.source,
        source_url=job.source_url,
        canonical_url=job.canonical_url,
        canonical_job_key=job.canonical_job_key,
        company_norm=job.company_norm,
        title_norm=job.title_norm,
        description_clean=job.description_clean,
        raw_sha256=job.raw_sha256,
        requirements=job.requirements,
        deadline_at=job.deadline_at,
        status=JobStatus(job.status),
        created_at=job.created_at,
    )

