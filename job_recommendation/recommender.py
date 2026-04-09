from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)

CRITICAL_REQUIRED_SKILLS = {
    "python",
    "java",
    "javascript",
    "typescript",
    "sql",
    "cybersecurity",
    "network security",
    "machine learning",
    "deep learning",
    "react",
    "django",
    "node.js",
}

# Phase 4: Structured fallback dataset with required/optional skills and per-role weight.
JOBS_DATASET: List[Dict[str, Any]] = [
    {
        "title": "Python Backend Developer",
        "required_skills": ["Python", "Django", "SQL"],
        "optional_skills": ["REST API", "Docker"],
        "weight": 1.0,
    },
    {
        "title": "Backend Engineer",
        "required_skills": ["Python", "Java", "SQL"],
        "optional_skills": ["Microservices", "Docker"],
        "weight": 0.9,
    },
    {
        "title": "Cybersecurity Analyst",
        "required_skills": ["Cybersecurity", "Network Security"],
        "optional_skills": ["Ethical Hacking", "Linux"],
        "weight": 1.1,
    },
    {
        "title": "AI Engineer",
        "required_skills": ["Python", "Machine Learning"],
        "optional_skills": ["Deep Learning", "TensorFlow"],
        "weight": 1.0,
    },
    {
        "title": "Full Stack Developer",
        "required_skills": ["JavaScript", "React", "Node.js", "SQL"],
        "optional_skills": ["TypeScript", "Docker", "REST API"],
        "weight": 1.0,
    },
    {
        "title": "Data Analyst",
        "required_skills": ["SQL", "Python", "Pandas"],
        "optional_skills": ["NumPy", "Tableau", "Power BI"],
        "weight": 0.95,
    },
    {
        "title": "Android Developer",
        "required_skills": ["Java", "Android Development"],
        "optional_skills": ["Kotlin", "REST API", "Git"],
        "weight": 0.9,
    },
    {
        "title": "DevOps Engineer",
        "required_skills": ["Docker", "Linux", "Git"],
        "optional_skills": ["Kubernetes", "AWS", "Jenkins"],
        "weight": 0.95,
    },
]


def _normalize_skill(value: str) -> str:
    skill = str(value or "").strip().lower()
    # Normalize separators so "full-stack" and "full stack" match.
    skill = skill.replace("&", " and ")
    skill = re.sub(r"[-_/]+", " ", skill)
    skill = re.sub(r"[^a-z0-9+#\.\s]", " ", skill)
    skill = re.sub(r"\s+", " ", skill).strip()
    return skill


def _tokenize_skill(skill: str) -> set[str]:
    normalized = _normalize_skill(skill)
    if not normalized:
        return set()
    # Full-word tokenization prevents false matches such as "c" vs "security".
    return set(re.findall(r"\b[a-z0-9+#\.]+\b", normalized))


def strict_match(resume_skill: str, job_skill: str) -> bool:
    # Exact match
    rs = _normalize_skill(resume_skill)
    js = _normalize_skill(job_skill)
    if not rs or not js:
        return False
    if rs == js:
        return True

    # Word-level match only
    rs_words = _tokenize_skill(rs)
    js_words = _tokenize_skill(js)

    # Must share at least one full token/word.
    return len(rs_words & js_words) > 0


def _skill_is_match(resume_skill: str, job_skill: str) -> bool:
    return strict_match(resume_skill, job_skill)


def skill_match(resume_skills: Iterable[str], job_skills: Iterable[str]) -> int:
    """Count matched skills with case-insensitive and partial matching."""
    normalized_resume = [_normalize_skill(skill) for skill in (resume_skills or []) if _normalize_skill(skill)]
    normalized_job = [_normalize_skill(skill) for skill in (job_skills or []) if _normalize_skill(skill)]
    if not normalized_resume or not normalized_job:
        return 0

    matched = 0
    used_resume_idx = set()
    for job_skill in normalized_job:
        for idx, resume_skill in enumerate(normalized_resume):
            if idx in used_resume_idx:
                continue
            if _skill_is_match(resume_skill, job_skill):
                matched += 1
                used_resume_idx.add(idx)
                break
    return matched


def _critical_bonus(resume_skills: Iterable[str]) -> float:
    normalized_resume = {_normalize_skill(skill) for skill in (resume_skills or []) if _normalize_skill(skill)}
    bonus = 0.0
    if any(_skill_is_match(skill, "python") for skill in normalized_resume):
        bonus += 0.03
    if any(_skill_is_match(skill, "cybersecurity") for skill in normalized_resume):
        bonus += 0.03
    if any(_skill_is_match(skill, "full stack") for skill in normalized_resume):
        bonus += 0.02
    return bonus


def _required_skill_weight(skill: str) -> int:
    normalized = _normalize_skill(skill)
    if normalized == "python":
        return 2
    if normalized in {"cybersecurity", "network security", "machine learning", "deep learning", "react", "django", "node.js"}:
        return 2
    return 1


def _weighted_required_match(resume_skills: Iterable[str], required_skills: Iterable[str]) -> float:
    required = [skill for skill in (required_skills or []) if _normalize_skill(skill)]
    if not required:
        return 0.0

    total_weight = sum(_required_skill_weight(skill) for skill in required)
    if total_weight <= 0:
        return 0.0

    matched_weight = 0
    for req_skill in required:
        if any(_skill_is_match(resume_skill, req_skill) for resume_skill in (resume_skills or [])):
            matched_weight += _required_skill_weight(req_skill)

    return matched_weight / total_weight


def _has_any_skill(resume_skills: Iterable[str], candidates: Iterable[str]) -> bool:
    return any(
        _skill_is_match(resume_skill, candidate)
        for resume_skill in (resume_skills or [])
        for candidate in (candidates or [])
    )


def is_relevant_domain(resume_skills: Iterable[str], job: Dict[str, Any]) -> bool:
    title = _normalize_skill(job.get("title", ""))
    required = [_normalize_skill(skill) for skill in (job.get("required_skills") or []) if _normalize_skill(skill)]

    is_cyber_job = "cyber" in title or "security" in title or any("security" in skill or "cyber" in skill for skill in required)
    is_ai_job = "ai" in title or "machine learning" in title or any(skill in {"machine learning", "artificial intelligence", "deep learning"} for skill in required)
    is_backend_job = "backend" in title or any(skill in {"python", "java", "django", "flask", "fastapi"} for skill in required)

    if is_cyber_job:
        return _has_any_skill(resume_skills, ["cybersecurity", "security", "network"])
    if is_ai_job:
        return _has_any_skill(resume_skills, ["machine learning", "ai", "artificial intelligence"])
    if is_backend_job:
        return _has_any_skill(resume_skills, ["python", "java", "backend"])
    return True


def _domain_boost(resume_skills: Iterable[str], job: Dict[str, Any]) -> float:
    normalized_resume = {_normalize_skill(skill) for skill in (resume_skills or []) if _normalize_skill(skill)}
    title = _normalize_skill(job.get("title", ""))
    required = [_normalize_skill(skill) for skill in (job.get("required_skills") or []) if _normalize_skill(skill)]

    boost = 0.0

    has_cyber_resume = any(_skill_is_match(skill, "cybersecurity") for skill in normalized_resume)
    is_cyber_job = (
        "cyber" in title
        or "security" in title
        or any("cyber" in skill or "security" in skill for skill in required)
    )
    if has_cyber_resume and is_cyber_job:
        boost += 0.05

    has_python_resume = any(_skill_is_match(skill, "python") for skill in normalized_resume)
    is_backend_job = (
        "backend" in title
        or ("python" in required and any(skill in required for skill in ["django", "flask", "fastapi"]))
    )
    if has_python_resume and is_backend_job:
        boost += 0.05

    return boost


def calculate_score(resume_skills: Iterable[str], job: Dict[str, Any]) -> float:
    """Weighted scoring: required=70%, optional=30%, then apply job weight and critical bonus."""
    required = job.get("required_skills") or []
    optional = job.get("optional_skills") or []
    weight = float(job.get("weight", 1.0) or 1.0)

    optional_total = len(optional)

    weighted_required_match = _weighted_required_match(resume_skills, required)
    required_match = weighted_required_match

    # Hard relevance cutoff: less than 50% required match is considered irrelevant.
    if required_match < 0.5:
        return 0.0

    matched_optional = skill_match(resume_skills, optional)
    optional_match = (matched_optional / optional_total) if optional_total > 0 else 0.0

    score = (required_match * 0.7 + optional_match * 0.3) * weight

    domain_valid = is_relevant_domain(resume_skills, job)
    if not domain_valid:
        score *= 0.3

    score += _critical_bonus(resume_skills)

    # Domain boost is only valid when there is required matching and domain is relevant.
    if required_match > 0 and domain_valid:
        score += _domain_boost(resume_skills, job)

    # Upper cap calibration: avoid inflated confidence.
    score = min(score, 0.85)

    # Final normalization bounds.
    score = max(0.05, min(score, 0.90))

    return score


def recommend_jobs(resume_skills: Iterable[str]) -> List[Dict[str, Any]]:
    """
    Phase 4 recommendation engine.

    Returns top 5 jobs with fields:
    - title
    - confidence (0-100)
    - score (0-1) for backend compatibility
    - job (alias for frontend compatibility)
    """
    resume_skills = [skill for skill in (resume_skills or []) if _normalize_skill(skill)]
    logger.info("Scoring recommendations for skills=%s", resume_skills)

    # Use curated dataset to keep scoring consistent and realistic across users.
    job_pool = JOBS_DATASET
    scored_jobs: List[Dict[str, Any]] = []

    for job in job_pool:
        score = calculate_score(resume_skills, job)
        if score < 0.25:
            print("Rejected job due to low match:", job)
            logger.info("Rejected job due to low match: %s", job)
            continue
        logger.info("Job match | title=%s | score=%.4f", job["title"], score)
        scored_jobs.append(
            {
                "title": job["title"],
                "confidence": int(round(score * 100)),
                "score": round(score, 2),
                "job": job["title"],
            }
        )

    scored_jobs.sort(key=lambda item: (-item["score"], item["title"].lower()))

    # Never return empty list.
    if not scored_jobs:
        logger.warning("No relevant jobs scored; returning default recommendation")
        return [
            {
                "title": "General Software Roles",
                "confidence": 10,
                "score": 0.10,
                "job": "General Software Roles",
            }
        ]

    top_jobs = scored_jobs[:5]
    logger.info("Top recommendations: %s", [{"title": item["title"], "score": item["score"]} for item in top_jobs])
    return top_jobs


def build_apply_links(job_title: str) -> Dict[str, str]:
    title = str(job_title or "").strip()
    encoded_title = quote_plus(title)
    slug_title = re.sub(r"[^a-z0-9]+", "-", _normalize_skill(title)).strip("-")

    return {
        "linkedin": f"https://www.linkedin.com/jobs/search/?keywords={encoded_title}",
        "naukri": f"https://www.naukri.com/{slug_title}-jobs" if slug_title else "https://www.naukri.com/",
    }


def build_featured_job(recommendations: List[Dict[str, Any]]) -> Dict[str, Any]:
    top_job = (recommendations or [{}])[0] or {}
    title = str(top_job.get("title") or top_job.get("job") or "General Software Roles").strip()
    confidence = int(top_job.get("confidence", round(float(top_job.get("score", 0.1)) * 100)))
    confidence = max(5, min(confidence, 90))

    return {
        "title": title,
        "confidence": confidence,
        "apply_links": build_apply_links(title),
    }


def get_job_profile_by_title(job_title: str) -> Dict[str, Any]:
    target = _normalize_skill(job_title)
    if not target:
        return {}

    for job in JOBS_DATASET:
        if _normalize_skill(job.get("title", "")) == target:
            return job

    return {}