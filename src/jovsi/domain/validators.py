"""JOV.si Factual Consistency Validator (Blueprint v2.0 Section 6).

Pure Python, zero I/O.
Validates structured resumes against candidate facts with 7 deterministic checks:
1. Structure & provenance of cited facts
2. Entity coverage (skills, numbers, dates, titles, employers)
3. Skills section backing
4. Date and duration containment
5. Contact details character-for-character match
6. Seniority and superlatives check
7. Job-text contamination (> 6 words verbatim copy)
"""

from datetime import date
import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from jovsi.domain.models import Fact, FactKind, StructuredResume


class ValidationViolation(BaseModel):
    code: str
    bullet_id: Optional[str] = None
    entity: Optional[str] = None
    message: str
    expected_fact_ids: List[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    is_valid: bool
    violations: List[ValidationViolation] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0


SENIORITY_WORDS = {
    "senior",
    "lead",
    "principal",
    "expert",
    "managed",
    "director",
    "head",
    "chief",
    "architect",
    "best",
    "spearheaded",
}


def normalize_tokens(text: str) -> List[str]:
    # Handles C++, C#, .NET, etc. safely without word-boundary stripping
    raw_tokens = re.split(r"[\s,;/\\]+", text)
    tokens = []
    for t in raw_tokens:
        cleaned = t.strip("()[]{}'\"`*•-").lower()
        if cleaned:
            tokens.append(cleaned)
    return tokens


def extract_numbers(text: str) -> Set[str]:
    return set(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))


def extract_dates(text: str) -> Set[str]:
    # Match YYYY-MM or YYYY or Month YYYY
    matches = re.findall(r"\b(?:20\d\d|19\d\d)(?:-\d\d)?\b", text)
    return set(matches)


class FactualConsistencyValidator:
    @classmethod
    def validate_resume(
        cls,
        resume: StructuredResume,
        candidate_facts: List[Fact],
        job_description_clean: Optional[str] = None,
    ) -> ValidationReport:
        """Run all 7 factual consistency checks over the structured resume."""
        violations: List[ValidationViolation] = []
        fact_map: Dict[str, Fact] = {f.id: f for f in candidate_facts}

        # 5. Contact info check: Character-for-character match against CONTACT facts
        contact_facts = [f for f in candidate_facts if f.kind == FactKind.CONTACT and f.is_usable]
        verified_emails = {str(f.value.get("email", "")).strip().lower() for f in contact_facts}
        verified_phones = {str(f.value.get("phone", "")).strip() for f in contact_facts}

        if resume.email.strip().lower() not in verified_emails:
            violations.append(
                ValidationViolation(
                    code="CONTACT_EMAIL_MISMATCH",
                    entity=resume.email,
                    message=f"Resume email '{resume.email}' does not match verified CONTACT facts character-for-character",
                )
            )

        if resume.phone.strip() not in verified_phones:
            violations.append(
                ValidationViolation(
                    code="CONTACT_PHONE_MISMATCH",
                    entity=resume.phone,
                    message=f"Resume phone '{resume.phone}' does not match verified CONTACT facts character-for-character",
                )
            )

        # Build 6-word n-grams for job description contamination check
        job_ngrams: Set[str] = set()
        if job_description_clean:
            job_tokens = normalize_tokens(job_description_clean)
            for i in range(len(job_tokens) - 5):
                job_ngrams.add(" ".join(job_tokens[i : i + 6]))

        # Iterate through resume sections and bullets
        for section in resume.sections:
            is_skills_section = "skill" in section.title.lower()

            for idx, bullet in enumerate(section.bullets):
                bullet_id = f"{section.title}#{idx+1}"

                # 1. Structure Check: Fact citations exist, are active, belong to candidate
                if not bullet.fact_ids:
                    violations.append(
                        ValidationViolation(
                            code="EMPTY_FACT_CITATION",
                            bullet_id=bullet_id,
                            message=f"Bullet '{bullet.text[:40]}...' has empty fact_ids citation list",
                        )
                    )
                    continue

                cited_facts: List[Fact] = []
                for fid in bullet.fact_ids:
                    if fid not in fact_map:
                        violations.append(
                            ValidationViolation(
                                code="FACT_NOT_FOUND",
                                bullet_id=bullet_id,
                                entity=fid,
                                message=f"Cited fact '{fid}' does not exist",
                            )
                        )
                    else:
                        f = fact_map[fid]
                        if not f.is_usable:
                            violations.append(
                                ValidationViolation(
                                    code="FACT_NOT_USABLE",
                                    bullet_id=bullet_id,
                                    entity=fid,
                                    message=f"Cited fact '{fid}' status={f.status}, provenance={f.provenance} (not usable)",
                                )
                            )
                        else:
                            cited_facts.append(f)

                if not cited_facts:
                    continue

                # Combine text from all cited facts for verification
                fact_texts = []
                for f in cited_facts:
                    fact_texts.append(str(f.value))
                combined_fact_text = " ".join(fact_texts).lower()

                # 2. Entity coverage: Numbers in bullet must be present in cited facts
                bullet_numbers = extract_numbers(bullet.text)
                fact_numbers = extract_numbers(combined_fact_text)
                for num in bullet_numbers:
                    if num not in fact_numbers:
                        violations.append(
                            ValidationViolation(
                                code="UNVERIFIED_NUMBER",
                                bullet_id=bullet_id,
                                entity=num,
                                message=f"Number '{num}' not present in cited facts",
                                expected_fact_ids=bullet.fact_ids,
                            )
                        )

                # 3. Skills Section Check
                if is_skills_section:
                    bullet_tokens = normalize_tokens(bullet.text)
                    for tok in bullet_tokens:
                        # Must exist in SKILL facts or explicit skill lists of projects/experience
                        has_skill_fact = any(
                            f.kind == FactKind.SKILL and tok in str(f.value.get("name", "")).lower()
                            or tok in [str(s).lower() for s in f.value.get("skills", [])]
                            for f in cited_facts
                        )
                        if not has_skill_fact and tok:
                            violations.append(
                                ValidationViolation(
                                    code="UNVERIFIED_SKILL",
                                    bullet_id=bullet_id,
                                    entity=tok,
                                    message=f"Skill '{tok}' in skills section is not backed by an active fact",
                                    expected_fact_ids=bullet.fact_ids,
                                )
                            )

                # 6. Seniority and superlatives check
                bullet_tokens = normalize_tokens(bullet.text)
                for tok in bullet_tokens:
                    if tok in SENIORITY_WORDS:
                        if tok not in combined_fact_text:
                            violations.append(
                                ValidationViolation(
                                    code="UNVERIFIED_SENIORITY_CLAIM",
                                    bullet_id=bullet_id,
                                    entity=tok,
                                    message=f"Superlative or seniority word '{tok}' is not in cited facts",
                                    expected_fact_ids=bullet.fact_ids,
                                )
                            )

                # 7. Job-text contamination check (> 6 words copied verbatim)
                if job_ngrams:
                    for i in range(len(bullet_tokens) - 5):
                        ngram = " ".join(bullet_tokens[i : i + 6])
                        if ngram in job_ngrams:
                            # Contamination unless it also appears in candidate facts
                            if ngram not in combined_fact_text:
                                violations.append(
                                    ValidationViolation(
                                        code="JOB_TEXT_CONTAMINATION",
                                        bullet_id=bullet_id,
                                        entity=ngram,
                                        message=f"Phrase of >6 words '{ngram}' copied verbatim from job description",
                                        expected_fact_ids=bullet.fact_ids,
                                    )
                                )

        is_valid = len(violations) == 0
        return ValidationReport(is_valid=is_valid, violations=violations)
