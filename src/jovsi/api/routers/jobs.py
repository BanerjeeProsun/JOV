"""Job Ingestion and Discovery API Router."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, select, distinct

from jovsi.adapters.db.session import get_db
from jovsi.adapters.db.models import (
    CandidateDB, FactDB, JobDB, JobLocationDB, JobSourceDB, UserDB,
    GeoCountryDB, GeoAdmin1DB, GeoCityDB, GeoAliasDB, EvaluationDB
)
from jovsi.api.dependencies import get_optional_current_user
from jovsi.adapters.sanitizer import UntrustedInputSanitizer
from jovsi.api.schemas import JobImportRequest, JobResponse
from jovsi.domain.models import DegreeLevel, Fact, FactKind, FactProvenance, FactStatus, Job, JobRequirements, JobStatus
from jovsi.services.geo import location_parser
from jovsi.services.job_discovery import JobDiscoveryService, SourceRegistryService
from jovsi.services.deep_links import DeepLinksService
from jovsi.services.manual_import import ManualImportService, RestrictedBoardError, JobExtractionError



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

    # Parse and index locations
    target_locs = requirements.target_locations or ["Remote"]
    for raw_loc in target_locs:
        for pl in location_parser.parse(raw_loc):
            db.add(
                JobLocationDB(
                    job_id=db_job.id,
                    country_code=pl.country,
                    admin1_code=pl.admin1,
                    city_id=pl.city,
                    work_mode=pl.work_mode_lower,
                    remote_scope=pl.remote_scope_lower,
                    raw_location=pl.raw,
                    confidence=pl.confidence,
                )
            )
    db.commit()

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


class UrlImportRequest(BaseModel):
    url: str


@router.post("/jobs/import/url", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def import_job_from_url(data: UrlImportRequest, db: Session = Depends(get_db)) -> JobResponse:
    try:
        extracted = ManualImportService.extract_from_url(data.url)
    except RestrictedBoardError as r_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(r_err),
        )
    except JobExtractionError as e_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e_err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import from URL: {exc}",
        )

    db_job = ManualImportService.import_and_persist(extracted, db)
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


class JobLocationResponse(BaseModel):
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    admin1_code: Optional[str] = None
    admin1_name: Optional[str] = None
    city_id: Optional[str] = None
    city_name: Optional[str] = None
    work_mode: str
    remote_scope: str
    raw_location: str


class JobSearchItem(BaseModel):
    id: str
    source: str
    source_url: str
    canonical_url: str
    company_name: str
    title: str
    description: str
    locations: List[JobLocationResponse] = []
    primary_location: str
    work_modes: List[str] = []
    required_skills: List[str] = []
    match_score: Optional[float] = None
    created_at: datetime


class CountryFacet(BaseModel):
    code: str
    name: str
    count: int


class Admin1Facet(BaseModel):
    country_code: str
    admin1_code: str
    name: str
    count: int


class CityFacet(BaseModel):
    id: str
    name: str
    country_code: str
    count: int


class KeyCountFacet(BaseModel):
    key: str
    label: str
    count: int


class JobSearchFacets(BaseModel):
    countries: List[CountryFacet] = []
    admin1: List[Admin1Facet] = []
    cities: List[CityFacet] = []
    work_modes: List[KeyCountFacet] = []
    sources: List[KeyCountFacet] = []


class JobSearchResponse(BaseModel):
    items: List[JobSearchItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    facets: JobSearchFacets


class LocationHierarchyResponse(BaseModel):
    countries: List[CountryFacet]
    admin1: List[Admin1Facet]
    cities: List[CityFacet]


def ensure_job_locations_backfilled(db: Session) -> None:
    """Ensure all jobs in DB have corresponding JobLocationDB rows."""
    jobs_without_loc = (
        db.query(JobDB)
        .outerjoin(JobLocationDB, JobDB.id == JobLocationDB.job_id)
        .filter(JobLocationDB.id.is_(None))
        .all()
    )
    for j in jobs_without_loc:
        reqs = j.requirements or {}
        target_locs = reqs.get("target_locations") or ["Remote"]
        for raw_loc in target_locs:
            for pl in location_parser.parse(raw_loc):
                db.add(
                    JobLocationDB(
                        job_id=j.id,
                        country_code=pl.country,
                        admin1_code=pl.admin1,
                        city_id=pl.city,
                        work_mode=pl.work_mode_lower,
                        remote_scope=pl.remote_scope_lower,
                        raw_location=pl.raw,
                        confidence=pl.confidence,
                    )
                )
    if jobs_without_loc:
        db.commit()


@router.get("/jobs/facets/locations", response_model=LocationHierarchyResponse)
def get_location_facets(
    country: Optional[str] = Query(None),
    admin1: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> LocationHierarchyResponse:
    ensure_job_locations_backfilled(db)

    # 1. Countries with counts
    c_stmt = (
        select(
            GeoCountryDB.code,
            GeoCountryDB.name,
            func.count(distinct(JobLocationDB.job_id)).label("count"),
        )
        .outerjoin(JobLocationDB, GeoCountryDB.code == JobLocationDB.country_code)
    )
    if q and q.strip():
        c_stmt = c_stmt.where(
            or_(
                func.lower(GeoCountryDB.name).ilike(f"%{q.strip().lower()}%"),
                func.lower(GeoCountryDB.code).ilike(f"%{q.strip().lower()}%"),
            )
        )
    c_stmt = c_stmt.group_by(GeoCountryDB.code, GeoCountryDB.name).order_by(
        func.count(distinct(JobLocationDB.job_id)).desc(),
        GeoCountryDB.name.asc(),
    ).limit(50)

    countries = [
        CountryFacet(code=r[0], name=r[1], count=r[2])
        for r in db.execute(c_stmt).all()
    ]

    # 2. Admin1 with counts
    a_stmt = (
        select(
            GeoAdmin1DB.country_code,
            GeoAdmin1DB.admin1_code,
            GeoAdmin1DB.name,
            func.count(distinct(JobLocationDB.job_id)).label("count"),
        )
        .outerjoin(
            JobLocationDB,
            and_(
                GeoAdmin1DB.country_code == JobLocationDB.country_code,
                GeoAdmin1DB.admin1_code == JobLocationDB.admin1_code,
            ),
        )
    )
    if country:
        a_stmt = a_stmt.where(GeoAdmin1DB.country_code == country.upper().strip())
    if q and q.strip():
        a_stmt = a_stmt.where(
            or_(
                func.lower(GeoAdmin1DB.name).ilike(f"%{q.strip().lower()}%"),
                func.lower(GeoAdmin1DB.admin1_code).ilike(f"%{q.strip().lower()}%"),
            )
        )
    a_stmt = a_stmt.group_by(
        GeoAdmin1DB.country_code, GeoAdmin1DB.admin1_code, GeoAdmin1DB.name
    ).order_by(
        func.count(distinct(JobLocationDB.job_id)).desc(),
        GeoAdmin1DB.name.asc(),
    ).limit(50)

    admin1_list = [
        Admin1Facet(country_code=r[0], admin1_code=r[1], name=r[2], count=r[3])
        for r in db.execute(a_stmt).all()
    ]

    # 3. Cities with counts
    city_stmt = (
        select(
            GeoCityDB.id,
            GeoCityDB.name,
            GeoCityDB.country_code,
            func.count(distinct(JobLocationDB.job_id)).label("count"),
        )
        .outerjoin(JobLocationDB, GeoCityDB.id == JobLocationDB.city_id)
    )
    if country:
        city_stmt = city_stmt.where(GeoCityDB.country_code == country.upper().strip())
    if admin1:
        city_stmt = city_stmt.where(GeoCityDB.admin1_code == admin1.upper().strip())
    if q and q.strip():
        city_stmt = city_stmt.where(func.lower(GeoCityDB.name).ilike(f"%{q.strip().lower()}%"))

    city_stmt = city_stmt.group_by(
        GeoCityDB.id, GeoCityDB.name, GeoCityDB.country_code
    ).order_by(
        func.count(distinct(JobLocationDB.job_id)).desc(),
        GeoCityDB.population.desc().nullslast(),
    ).limit(50)

    cities = [
        CityFacet(id=r[0], name=r[1], country_code=r[2], count=r[3])
        for r in db.execute(city_stmt).all()
    ]

    return LocationHierarchyResponse(countries=countries, admin1=admin1_list, cities=cities)


@router.get("/jobs/search", response_model=JobSearchResponse)
def search_jobs(
    q: Optional[str] = Query(None),
    country: Optional[List[str]] = Query(None),
    admin1: Optional[List[str]] = Query(None),
    city: Optional[List[str]] = Query(None),
    work_mode: Optional[List[str]] = Query(None),
    remote_scope: Optional[List[str]] = Query(None),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    source: Optional[List[str]] = Query(None),
    sort: str = Query("date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    candidate_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> JobSearchResponse:
    ensure_job_locations_backfilled(db)

    # Base query for active jobs
    base_stmt = select(JobDB).where(JobDB.status == "ACTIVE")

    # Keyword search across title, company, clean description
    if q and q.strip():
        q_clean = f"%{q.strip().lower()}%"
        base_stmt = base_stmt.where(
            or_(
                func.lower(JobDB.title_norm).ilike(q_clean),
                func.lower(JobDB.company_norm).ilike(q_clean),
                func.lower(JobDB.description_clean).ilike(q_clean),
            )
        )

    # Source filtering
    if source:
        clean_sources = [s.strip().lower() for s in source if s.strip()]
        if clean_sources:
            base_stmt = base_stmt.where(func.lower(JobDB.source).in_(clean_sources))

    # Location & Work Mode filtering
    loc_conditions = []
    if country:
        c_list = [c.upper().strip() for c in country if c.strip()]
        if c_list:
            if work_mode and "remote" in [w.lower() for w in work_mode]:
                loc_conditions.append(
                    or_(
                        JobLocationDB.country_code.in_(c_list),
                        and_(JobLocationDB.work_mode == "remote", JobLocationDB.remote_scope == "global"),
                    )
                )
            else:
                loc_conditions.append(JobLocationDB.country_code.in_(c_list))

    if admin1:
        a_list = [a.upper().strip() for a in admin1 if a.strip()]
        if a_list:
            loc_conditions.append(JobLocationDB.admin1_code.in_(a_list))

    if city:
        city_list = [c.strip() for c in city if c.strip()]
        if city_list:
            loc_conditions.append(
                or_(
                    JobLocationDB.city_id.in_(city_list),
                    func.lower(JobLocationDB.raw_location).in_([c.lower() for c in city_list]),
                )
            )

    if work_mode:
        wm_list = [w.lower().strip() for w in work_mode if w.strip()]
        if wm_list:
            loc_conditions.append(JobLocationDB.work_mode.in_(wm_list))

    if remote_scope:
        rs_list = [r.lower().strip() for r in remote_scope if r.strip()]
        if rs_list:
            loc_conditions.append(JobLocationDB.remote_scope.in_(rs_list))

    if loc_conditions:
        loc_subq = (
            select(JobLocationDB.job_id)
            .where(and_(*loc_conditions))
            .distinct()
            .scalar_subquery()
        )
        base_stmt = base_stmt.where(JobDB.id.in_(loc_subq))

    # Candidate evaluation / score floor filter
    if candidate_id and min_score is not None:
        eval_subq = (
            select(EvaluationDB.job_id)
            .where(
                EvaluationDB.candidate_id == candidate_id,
                EvaluationDB.score_total >= min_score,
            )
            .scalar_subquery()
        )
        base_stmt = base_stmt.where(JobDB.id.in_(eval_subq))

    # Total matching jobs
    total_matching = db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0
    total_pages = max(1, (total_matching + page_size - 1) // page_size)

    # Pagination and sorting
    if sort == "date":
        exec_stmt = base_stmt.order_by(JobDB.created_at.desc())
    else:
        exec_stmt = base_stmt.order_by(JobDB.created_at.desc())

    exec_stmt = exec_stmt.offset((page - 1) * page_size).limit(page_size)
    page_jobs = db.scalars(exec_stmt).all()

    # Batch load locations for page jobs
    job_ids = [j.id for j in page_jobs]
    locations_by_job: Dict[str, List[JobLocationResponse]] = {jid: [] for jid in job_ids}
    if job_ids:
        loc_rows = (
            db.execute(
                select(
                    JobLocationDB.job_id,
                    JobLocationDB.country_code,
                    GeoCountryDB.name,
                    JobLocationDB.admin1_code,
                    GeoAdmin1DB.name,
                    JobLocationDB.city_id,
                    GeoCityDB.name,
                    JobLocationDB.work_mode,
                    JobLocationDB.remote_scope,
                    JobLocationDB.raw_location,
                )
                .outerjoin(GeoCountryDB, JobLocationDB.country_code == GeoCountryDB.code)
                .outerjoin(
                    GeoAdmin1DB,
                    and_(
                        JobLocationDB.country_code == GeoAdmin1DB.country_code,
                        JobLocationDB.admin1_code == GeoAdmin1DB.admin1_code,
                    ),
                )
                .outerjoin(GeoCityDB, JobLocationDB.city_id == GeoCityDB.id)
                .where(JobLocationDB.job_id.in_(job_ids))
            ).all()
        )
        for r in loc_rows:
            jid = r[0]
            if jid in locations_by_job:
                locations_by_job[jid].append(
                    JobLocationResponse(
                        country_code=r[1],
                        country_name=r[2],
                        admin1_code=r[3],
                        admin1_name=r[4],
                        city_id=r[5],
                        city_name=r[6],
                        work_mode=r[7],
                        remote_scope=r[8],
                        raw_location=r[9],
                    )
                )

    # Batch load candidate evaluations if candidate_id provided
    scores_by_job: Dict[str, float] = {}
    if candidate_id and job_ids:
        eval_rows = db.execute(
            select(EvaluationDB.job_id, EvaluationDB.score_total)
            .where(
                EvaluationDB.candidate_id == candidate_id,
                EvaluationDB.job_id.in_(job_ids),
            )
        ).all()
        for ejid, escore in eval_rows:
            scores_by_job[ejid] = escore

    # Build items list
    items: List[JobSearchItem] = []
    for j in page_jobs:
        j_locs = locations_by_job.get(j.id, [])
        primary_loc = j_locs[0].raw_location if j_locs else "Remote / Flexible"
        w_modes = list({loc.work_mode for loc in j_locs if loc.work_mode != "unspecified"})
        if not w_modes:
            w_modes = (j.requirements or {}).get("accepted_work_modes", ["remote", "hybrid", "onsite"])

        items.append(
            JobSearchItem(
                id=j.id,
                source=j.source,
                source_url=j.source_url,
                canonical_url=j.canonical_url,
                company_name=j.company_norm,
                title=j.title_norm,
                description=j.description_clean,
                locations=j_locs,
                primary_location=primary_loc,
                work_modes=w_modes,
                required_skills=(j.requirements or {}).get("required_skills", []),
                match_score=scores_by_job.get(j.id),
                created_at=j.created_at,
            )
        )

    # Computed facet breakdown for current keyword query
    facet_job_stmt = select(JobDB.id).where(JobDB.status == "ACTIVE")
    if q and q.strip():
        q_clean = f"%{q.strip().lower()}%"
        facet_job_stmt = facet_job_stmt.where(
            or_(
                func.lower(JobDB.title_norm).ilike(q_clean),
                func.lower(JobDB.company_norm).ilike(q_clean),
                func.lower(JobDB.description_clean).ilike(q_clean),
            )
        )
    facet_subq = facet_job_stmt.scalar_subquery()

    # 1. Countries
    country_facets = [
        CountryFacet(code=r[0], name=r[1] or r[0], count=r[2])
        for r in db.execute(
            select(
                JobLocationDB.country_code,
                GeoCountryDB.name,
                func.count(distinct(JobLocationDB.job_id)).label("count"),
            )
            .outerjoin(GeoCountryDB, JobLocationDB.country_code == GeoCountryDB.code)
            .where(JobLocationDB.job_id.in_(facet_subq), JobLocationDB.country_code.isnot(None))
            .group_by(JobLocationDB.country_code, GeoCountryDB.name)
            .order_by(func.count(distinct(JobLocationDB.job_id)).desc())
            .limit(20)
        ).all()
    ]

    # 2. Admin1
    admin1_facets = [
        Admin1Facet(country_code=r[0], admin1_code=r[1], name=r[2] or r[1], count=r[3])
        for r in db.execute(
            select(
                JobLocationDB.country_code,
                JobLocationDB.admin1_code,
                GeoAdmin1DB.name,
                func.count(distinct(JobLocationDB.job_id)).label("count"),
            )
            .outerjoin(
                GeoAdmin1DB,
                and_(
                    JobLocationDB.country_code == GeoAdmin1DB.country_code,
                    JobLocationDB.admin1_code == GeoAdmin1DB.admin1_code,
                ),
            )
            .where(JobLocationDB.job_id.in_(facet_subq), JobLocationDB.admin1_code.isnot(None))
            .group_by(JobLocationDB.country_code, JobLocationDB.admin1_code, GeoAdmin1DB.name)
            .order_by(func.count(distinct(JobLocationDB.job_id)).desc())
            .limit(20)
        ).all()
    ]

    # 3. Cities
    city_facets = [
        CityFacet(id=r[0], name=r[1] or r[0], country_code=r[2] or "", count=r[3])
        for r in db.execute(
            select(
                JobLocationDB.city_id,
                GeoCityDB.name,
                JobLocationDB.country_code,
                func.count(distinct(JobLocationDB.job_id)).label("count"),
            )
            .outerjoin(GeoCityDB, JobLocationDB.city_id == GeoCityDB.id)
            .where(JobLocationDB.job_id.in_(facet_subq), JobLocationDB.city_id.isnot(None))
            .group_by(JobLocationDB.city_id, GeoCityDB.name, JobLocationDB.country_code)
            .order_by(func.count(distinct(JobLocationDB.job_id)).desc())
            .limit(20)
        ).all()
    ]

    # 4. Work Modes
    wm_labels = {"remote": "Remote", "hybrid": "Hybrid", "onsite": "On-site"}
    wm_facets = [
        KeyCountFacet(key=r[0], label=wm_labels.get(r[0], r[0].capitalize()), count=r[1])
        for r in db.execute(
            select(
                JobLocationDB.work_mode,
                func.count(distinct(JobLocationDB.job_id)).label("count"),
            )
            .where(JobLocationDB.job_id.in_(facet_subq), JobLocationDB.work_mode != "unspecified")
            .group_by(JobLocationDB.work_mode)
            .order_by(func.count(distinct(JobLocationDB.job_id)).desc())
        ).all()
    ]

    # 5. Sources
    src_labels = {
        "greenhouse": "Greenhouse",
        "lever": "Lever",
        "ashby": "Ashby",
        "smartrecruiters": "SmartRecruiters",
        "jobicy": "Jobicy",
        "manual_import": "Manual Import",
    }
    src_facets = [
        KeyCountFacet(key=r[0], label=src_labels.get(r[0], r[0].capitalize()), count=r[1])
        for r in db.execute(
            select(
                JobDB.source,
                func.count(JobDB.id).label("count"),
            )
            .where(JobDB.id.in_(facet_subq))
            .group_by(JobDB.source)
            .order_by(func.count(JobDB.id).desc())
        ).all()
    ]

    facets = JobSearchFacets(
        countries=country_facets,
        admin1=admin1_facets,
        cities=city_facets,
        work_modes=wm_facets,
        sources=src_facets,
    )

    return JobSearchResponse(
        items=items,
        total=total_matching,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        facets=facets,
    )


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


class EmployerSourceRequest(BaseModel):
    provider: str
    employer_name: str
    board_identifier: str


class EmployerSourceResponse(BaseModel):
    id: str
    provider: str
    employer_name: str
    board_identifier: str
    status: str
    last_job_count: int
    last_probed_at: Optional[datetime] = None
    last_error: Optional[str] = None


@router.get("/jobs/sources", response_model=List[Dict[str, Any]])
def get_job_sources(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    return JobDiscoveryService.get_registered_sources(db=db)


@router.get("/jobs/sources/employers", response_model=List[EmployerSourceResponse])
def list_employer_sources(
    provider: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[EmployerSourceResponse]:
    stmt = select(JobSourceDB)
    if provider:
        stmt = stmt.where(JobSourceDB.provider == provider)
    stmt = stmt.order_by(JobSourceDB.provider, JobSourceDB.employer_name)
    rows = db.scalars(stmt).all()
    return [
        EmployerSourceResponse(
            id=r.id,
            provider=r.provider,
            employer_name=r.employer_name,
            board_identifier=r.board_identifier,
            status=r.status,
            last_job_count=r.last_job_count,
            last_probed_at=r.last_probed_at,
            last_error=r.last_error,
        )
        for r in rows
    ]


@router.post("/jobs/sources/employers", response_model=EmployerSourceResponse, status_code=status.HTTP_201_CREATED)
def add_employer_source(
    data: EmployerSourceRequest,
    db: Session = Depends(get_db),
) -> EmployerSourceResponse:
    existing = db.scalar(
        select(JobSourceDB).where(
            JobSourceDB.provider == data.provider.lower().strip(),
            JobSourceDB.board_identifier == data.board_identifier.lower().strip(),
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="Employer board already registered")

    new_src = JobSourceDB(
        provider=data.provider.lower().strip(),
        employer_name=data.employer_name.strip(),
        board_identifier=data.board_identifier.lower().strip(),
        status="untested",
    )
    db.add(new_src)
    db.commit()
    db.refresh(new_src)

    probed = SourceRegistryService.probe_source(new_src.id, db)
    return EmployerSourceResponse(
        id=probed.id,
        provider=probed.provider,
        employer_name=probed.employer_name,
        board_identifier=probed.board_identifier,
        status=probed.status,
        last_job_count=probed.last_job_count,
        last_probed_at=probed.last_probed_at,
        last_error=probed.last_error,
    )


@router.post("/jobs/sources/{source_id}/probe", response_model=EmployerSourceResponse)
def probe_employer_source(
    source_id: str,
    db: Session = Depends(get_db),
) -> EmployerSourceResponse:
    try:
        probed = SourceRegistryService.probe_source(source_id, db)
        return EmployerSourceResponse(
            id=probed.id,
            provider=probed.provider,
            employer_name=probed.employer_name,
            board_identifier=probed.board_identifier,
            status=probed.status,
            last_job_count=probed.last_job_count,
            last_probed_at=probed.last_probed_at,
            last_error=probed.last_error,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class SourceHealthTelemetry(BaseModel):
    provider: str
    name: str
    category: str
    status: str
    latency_ms: Optional[float] = None
    policy_status: str
    error: Optional[str] = None
    last_checked_at: str


@router.get("/jobs/sources/health", response_model=List[SourceHealthTelemetry])
def get_sources_health(db: Session = Depends(get_db)) -> List[SourceHealthTelemetry]:
    return SourceRegistryService.check_all_sources_health(db=db)


class DeepLinkResponseItem(BaseModel):
    id: str
    name: str
    url: str
    policy_status: str
    policy_reason: str
    supported_alternatives: List[str]


@router.get("/jobs/deep-links", response_model=List[DeepLinkResponseItem])
def get_deep_links(
    query: str = Query("", description="Keyword search query"),
    location: str = Query("", description="Geographic location filter"),
) -> List[DeepLinkResponseItem]:
    return DeepLinksService.generate_links(query=query, location=location)


@router.post("/jobs/discover", response_model=DiscoverJobsResponse)
def discover_jobs(
    data: DiscoverJobsRequest,
    current_user: Optional[UserDB] = Depends(get_optional_current_user),
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
        cand = db.scalar(select(CandidateDB).where(CandidateDB.id == data.candidate_id))
        if cand and cand.user_id:
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            if cand.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied: Candidate belongs to another account")

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

            # Milestone 6: Parse location and store in job_locations
            raw_loc = item.get("location", "Remote / Flexible")
            for pl in location_parser.parse(raw_loc):
                db.add(
                    JobLocationDB(
                        job_id=existing.id,
                        country_code=pl.country,
                        admin1_code=pl.admin1,
                        city_id=pl.city,
                        work_mode=pl.work_mode_lower,
                        remote_scope=pl.remote_scope_lower,
                        raw_location=pl.raw,
                        confidence=pl.confidence,
                    )
                )
            db.commit()

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

