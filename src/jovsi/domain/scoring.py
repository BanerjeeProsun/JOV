"""JOV.si Suitability Scoring Engine (Blueprint v2.0 Section 7).

Pure Python, zero I/O.
100-point soft score model:
- Skills alignment (35 pts)
- Projects & experience (25 pts)
- Education (15 pts)
- Role and career (15 pts)
- Location and mode (10 pts)
Supports dynamic renormalisation and produces a transparent explanation payload.
"""

import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from jovsi.domain.models import Fact, FactKind, JobRequirements


class CategoryScore(BaseModel):
    category_name: str
    earned_points: float
    available_points: float
    matched_items: List[str] = Field(default_factory=list)
    missing_items: List[str] = Field(default_factory=list)
    fact_ids_used: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class EvaluationScore(BaseModel):
    total_score: float  # 0 to 100
    is_low_confidence: bool
    formula_version: str = "v2.0"
    categories: Dict[str, CategoryScore]
    summary_explanation: str
    improvement_hints: List[str] = Field(default_factory=list)


# Related fields ontology for education
RELATED_FIELDS = {
    "computer science": {"software engineering", "data science", "statistics", "mathematics", "information technology"},
    "data science": {"computer science", "statistics", "mathematics", "analytics"},
    "software engineering": {"computer science", "information technology"},
}

# Skill alias mappings
SKILL_ALIASES = {
    "sklearn": "scikit-learn",
    "scikit-learn": "scikit-learn",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "py": "python",
    "python": "python",
    "fastapi": "fastapi",
    "react": "react",
    "reactjs": "react",
    "typescript": "typescript",
    "ts": "typescript",
}


def canonical_skill(name: str) -> str:
    cleaned = name.strip().lower()
    return SKILL_ALIASES.get(cleaned, cleaned)


def tokenize(text: str) -> Set[str]:
    return set(re.findall(r"\b[a-zA-Z0-9_+#.-]+\b", text.lower()))


def token_similarity(a: str, b: str) -> float:
    tokens_a = tokenize(a)
    tokens_b = tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return len(intersection) / len(union)


class ScoringEngine:
    @classmethod
    def score_job(
        cls,
        requirements: JobRequirements,
        active_facts: List[Fact],
        candidate_target_titles: Optional[List[str]] = None,
        candidate_role_family: Optional[str] = None,
        candidate_seniority: Optional[str] = None,
        candidate_work_modes: Optional[List[str]] = None,
        candidate_locations: Optional[List[str]] = None,
    ) -> EvaluationScore:
        """Pure function calculating the 100-point suitability score and explanation."""
        usable_facts = [f for f in active_facts if f.is_usable]
        categories: Dict[str, CategoryScore] = {}

        # 1. Skills alignment (35 pts)
        cat_skills = cls._score_skills(requirements, usable_facts)
        categories["skills"] = cat_skills

        # 2. Projects & Experience (25 pts)
        cat_exp = cls._score_experience(requirements, usable_facts)
        categories["experience"] = cat_exp

        # 3. Education (15 pts)
        cat_edu = cls._score_education(requirements, usable_facts)
        categories["education"] = cat_edu

        # 4. Role & Career (15 pts)
        cat_role = cls._score_role(
            requirements,
            candidate_target_titles or [],
            candidate_role_family,
            candidate_seniority,
        )
        categories["role"] = cat_role

        # 5. Location & Mode (10 pts)
        cat_loc = cls._score_location(
            requirements,
            candidate_work_modes or ["remote"],
            candidate_locations or [],
        )
        categories["location"] = cat_loc

        # Renormalisation: score = 100 * (earned / available)
        total_earned = sum(c.earned_points for c in categories.values())
        total_available = sum(c.available_points for c in categories.values())

        if total_available > 0:
            final_score = round(100.0 * (total_earned / total_available), 2)
        else:
            final_score = 0.0

        is_low_confidence = total_available < 50.0

        # Construct explanation and improvement hints
        hints = []
        if cat_skills.missing_items:
            hints.append(f"Add verified skills: {', '.join(cat_skills.missing_items[:3])}")
        if cat_exp.missing_items:
            hints.append(f"Add experience aligning with: {cat_exp.missing_items[0]}")

        summary = f"Scored {final_score}/100 across {total_available:.0f} available points."
        if is_low_confidence:
            summary += " (LOW CONFIDENCE: job lacks sufficient constraint details)."

        return EvaluationScore(
            total_score=final_score,
            is_low_confidence=is_low_confidence,
            categories=categories,
            summary_explanation=summary,
            improvement_hints=hints,
        )

    @classmethod
    def _score_skills(cls, req: JobRequirements, facts: List[Fact]) -> CategoryScore:
        # Extract candidate verified skills
        candidate_skills: Set[str] = set()
        fact_ids: List[str] = []
        for f in facts:
            if f.kind == FactKind.SKILL:
                s_name = canonical_skill(str(f.value.get("name", "")))
                if s_name:
                    candidate_skills.add(s_name)
                    fact_ids.append(f.id)
            elif f.kind in (FactKind.PROJECT, FactKind.EXPERIENCE):
                for s in f.value.get("skills", []):
                    s_name = canonical_skill(str(s))
                    if s_name:
                        candidate_skills.add(s_name)
                        if f.id not in fact_ids:
                            fact_ids.append(f.id)

        req_skills = [canonical_skill(s) for s in req.required_skills if s.strip()]
        pref_skills = [canonical_skill(s) for s in req.preferred_skills if s.strip()]

        if not req_skills and not pref_skills:
            # Excluded from available points if job has no skills data
            return CategoryScore(
                category_name="skills",
                earned_points=0.0,
                available_points=0.0,
                notes="Job specifies no required or preferred skills",
            )

        matched_req = [s for s in req_skills if s in candidate_skills]
        missing_req = [s for s in req_skills if s not in candidate_skills]

        matched_pref = [s for s in pref_skills if s in candidate_skills]
        missing_pref = [s for s in pref_skills if s not in candidate_skills]

        r_ratio = (len(matched_req) / len(req_skills)) if req_skills else 1.0
        p_ratio = (len(matched_pref) / len(pref_skills)) if pref_skills else 1.0

        if req_skills and pref_skills:
            earned = 35.0 * (0.75 * r_ratio + 0.25 * p_ratio)
        elif req_skills:
            earned = 35.0 * r_ratio
        else:
            earned = 35.0 * p_ratio

        return CategoryScore(
            category_name="skills",
            earned_points=round(earned, 2),
            available_points=35.0,
            matched_items=matched_req + matched_pref,
            missing_items=missing_req + missing_pref,
            fact_ids_used=fact_ids,
        )

    @classmethod
    def _score_experience(cls, req: JobRequirements, facts: List[Fact]) -> CategoryScore:
        responsibilities = req.responsibilities[:12]
        if not responsibilities:
            return CategoryScore(
                category_name="experience",
                earned_points=0.0,
                available_points=0.0,
                notes="Job specifies no responsibilities",
            )

        # Collect candidate project and experience bullets
        bullets: List[Tuple[str, str]] = []  # (text, fact_id)
        for f in facts:
            if f.kind in (FactKind.EXPERIENCE, FactKind.PROJECT):
                text_content = str(f.value.get("description", ""))
                if text_content:
                    bullets.append((text_content, f.id))
                for b in f.value.get("bullets", []):
                    bullets.append((str(b), f.id))

        if not bullets:
            return CategoryScore(
                category_name="experience",
                earned_points=0.0,
                available_points=25.0,
                missing_items=responsibilities,
            )

        # Saturation point s* = 0.5
        s_star = 0.5
        sim_scores = []
        fact_ids_used = set()
        matched = []
        missing = []

        for resp in responsibilities:
            best_sim = 0.0
            best_fact_id = None
            for b_text, f_id in bullets:
                sim = token_similarity(resp, b_text)
                if sim > best_sim:
                    best_sim = sim
                    best_fact_id = f_id
            
            sim_scores.append(min(1.0, best_sim / s_star))
            if best_sim >= 0.2:
                matched.append(resp[:60] + "...")
                if best_fact_id:
                    fact_ids_used.add(best_fact_id)
            else:
                missing.append(resp[:60] + "...")

        avg_sat = sum(sim_scores) / len(sim_scores)
        earned = round(25.0 * avg_sat, 2)

        return CategoryScore(
            category_name="experience",
            earned_points=earned,
            available_points=25.0,
            matched_items=matched,
            missing_items=missing,
            fact_ids_used=list(fact_ids_used),
        )

    @classmethod
    def _score_education(cls, req: JobRequirements, facts: List[Fact]) -> CategoryScore:
        if req.min_degree is None and req.target_role_family is None:
            return CategoryScore(
                category_name="education",
                earned_points=0.0,
                available_points=0.0,
                notes="Job specifies no education constraints",
            )

        edu_facts = [f for f in facts if f.kind == FactKind.EDUCATION]
        if not edu_facts:
            return CategoryScore(
                category_name="education",
                earned_points=0.0,
                available_points=15.0,
                missing_items=["No verified education facts"],
            )

        # Field alignment (10 pts)
        earned_field = 0.0
        field_matches = []
        fact_ids = []
        target_role = (req.target_role_family or "").lower()

        for f in edu_facts:
            cand_field = str(f.value.get("field", "")).lower()
            if not cand_field:
                continue
            fact_ids.append(f.id)
            if target_role and (target_role in cand_field or cand_field in target_role):
                earned_field = max(earned_field, 10.0)
                field_matches.append(cand_field)
            else:
                related = RELATED_FIELDS.get(target_role, set())
                if any(r in cand_field for r in related):
                    earned_field = max(earned_field, 6.0)
                    field_matches.append(f"{cand_field} (related)")
                else:
                    earned_field = max(earned_field, 4.0)  # general STEM base

        # Coursework overlap (5 pts)
        earned_course = 5.0  # default baseline if coursework not specified

        return CategoryScore(
            category_name="education",
            earned_points=round(earned_field + earned_course, 2),
            available_points=15.0,
            matched_items=field_matches,
            fact_ids_used=fact_ids,
        )

    @classmethod
    def _score_role(
        cls,
        req: JobRequirements,
        candidate_target_titles: List[str],
        candidate_role_family: Optional[str],
        candidate_seniority: Optional[str],
    ) -> CategoryScore:
        job_role_family = (req.target_role_family or "").lower()
        if not job_role_family and not candidate_target_titles:
            return CategoryScore(
                category_name="role",
                earned_points=0.0,
                available_points=0.0,
                notes="Job specifies no target role metadata",
            )

        earned_title = 0.0
        matches = []
        for t in candidate_target_titles:
            t_low = t.lower()
            if job_role_family and t_low == job_role_family:
                earned_title = max(earned_title, 10.0)
                matches.append(t)
            elif job_role_family and (t_low in job_role_family or job_role_family in t_low):
                earned_title = max(earned_title, 7.0)
                matches.append(t)
            elif token_similarity(t_low, job_role_family) >= 0.5:
                earned_title = max(earned_title, 4.0)
                matches.append(t)

        earned_seniority = 3.0
        earned_emp_type = 2.0
        total_role = round(earned_title + earned_seniority + earned_emp_type, 2)

        return CategoryScore(
            category_name="role",
            earned_points=total_role,
            available_points=15.0,
            matched_items=matches,
        )

    @classmethod
    def _score_location(
        cls,
        req: JobRequirements,
        candidate_work_modes: List[str],
        candidate_locations: List[str],
    ) -> CategoryScore:
        if not req.accepted_work_modes and not req.target_locations:
            return CategoryScore(
                category_name="location",
                earned_points=0.0,
                available_points=0.0,
                notes="Job specifies no location constraints",
            )

        # Mode match (6 pts)
        job_modes = {m.lower() for m in req.accepted_work_modes}
        cand_modes = {m.lower() for m in candidate_work_modes}
        earned_mode = 6.0 if job_modes.intersection(cand_modes) else 0.0

        # Location match (4 pts)
        earned_loc = 0.0
        if "remote" in job_modes and "remote" in cand_modes:
            earned_loc = 4.0
        elif any(loc.lower() in [tl.lower() for tl in req.target_locations] for loc in candidate_locations):
            earned_loc = 4.0

        return CategoryScore(
            category_name="location",
            earned_points=round(earned_mode + earned_loc, 2),
            available_points=10.0,
            matched_items=list(job_modes.intersection(cand_modes)),
        )
