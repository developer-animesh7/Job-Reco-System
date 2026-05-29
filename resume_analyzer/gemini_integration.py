"""
Local resume intelligence helpers.

This module keeps the previous public function names used by the views, but it
does all extraction and recommendation support with written code. No external AI
or network API is configured or called.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)


SKILL_ALIASES: Dict[str, Iterable[str]] = {
    "Python": ("python",),
    "Java": ("java",),
    "C": (" c ",),
    "C++": ("c++", "cpp"),
    "C#": ("c#", "c sharp"),
    "JavaScript": ("javascript", "java script", "js"),
    "TypeScript": ("typescript", "type script", "ts"),
    "Kotlin": ("kotlin",),
    "Swift": ("swift",),
    "Go": ("golang", " go "),
    "Rust": ("rust",),
    "PHP": ("php",),
    "Ruby": ("ruby",),
    "Django": ("django",),
    "Flask": ("flask",),
    "FastAPI": ("fastapi", "fast api"),
    "React": ("react", "react.js", "reactjs"),
    "Vue": ("vue", "vue.js", "vuejs"),
    "Angular": ("angular",),
    "Node.js": ("node.js", "nodejs", "node js"),
    "Express": ("express", "express.js"),
    "Spring Boot": ("spring boot", "springboot"),
    "HTML": ("html",),
    "CSS": ("css",),
    "SQL": ("sql",),
    "PostgreSQL": ("postgresql", "postgres"),
    "MySQL": ("mysql",),
    "MongoDB": ("mongodb", "mongo db"),
    "Redis": ("redis",),
    "Elasticsearch": ("elasticsearch", "elastic search"),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure",),
    "GCP": ("gcp", "google cloud"),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "Terraform": ("terraform",),
    "Jenkins": ("jenkins",),
    "GitHub Actions": ("github actions",),
    "Git": ("git",),
    "Linux": ("linux",),
    "Machine Learning": ("machine learning", "ml"),
    "Deep Learning": ("deep learning",),
    "Artificial Intelligence": ("artificial intelligence", " ai "),
    "NLP": ("nlp", "natural language processing"),
    "Computer Vision": ("computer vision",),
    "TensorFlow": ("tensorflow",),
    "PyTorch": ("pytorch",),
    "Keras": ("keras",),
    "Scikit-learn": ("scikit-learn", "scikit learn", "sklearn"),
    "Pandas": ("pandas",),
    "NumPy": ("numpy",),
    "Tableau": ("tableau",),
    "Power BI": ("power bi", "powerbi"),
    "Cybersecurity": ("cybersecurity", "cyber security"),
    "Network Security": ("network security",),
    "Ethical Hacking": ("ethical hacking",),
    "Penetration Testing": ("penetration testing",),
    "REST API": ("rest api", "restful api", "rest"),
    "GraphQL": ("graphql",),
    "Microservices": ("microservices", "micro services"),
    "Agile": ("agile",),
    "Scrum": ("scrum",),
    "Full Stack": ("full stack", "full-stack", "fullstack"),
    "Android Development": ("android development", "android"),
    "iOS Development": ("ios development", "ios"),
}

ROLE_KEYWORDS: Dict[str, Iterable[str]] = {
    "Backend Developer": ("backend developer", "backend engineer", "django developer"),
    "Frontend Developer": ("frontend developer", "front end developer", "react developer"),
    "Full Stack Developer": ("full stack developer", "full-stack developer"),
    "Data Analyst": ("data analyst", "business analyst"),
    "Data Scientist": ("data scientist", "machine learning engineer", "ml engineer"),
    "DevOps Engineer": ("devops engineer", "cloud engineer", "site reliability engineer"),
    "Cybersecurity Analyst": ("cybersecurity analyst", "security analyst", "soc analyst"),
    "Mobile Developer": ("android developer", "ios developer", "mobile developer"),
}

EDUCATION_PATTERNS = (
    r"\b(?:bachelor|b\.tech|btech|b\.e\.|be|bsc|b\.sc|bca)\b[^.\n,;]*",
    r"\b(?:master|m\.tech|mtech|m\.e\.|me|msc|m\.sc|mca|mba)\b[^.\n,;]*",
    r"\b(?:phd|doctorate)\b[^.\n,;]*",
    r"\b(?:computer science|information technology|data science)\b[^.\n,;]*",
)

NAME_LABEL_RE = re.compile(r"\b(?:name|candidate)\s*[:\-]\s*([A-Z][A-Za-z .'-]{2,80})", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
YEAR_RANGE_RE = re.compile(r"\b(?:19|20)\d{2}\s*(?:-|to|–)\s*(?:(?:19|20)\d{2}|present|current)\b", re.IGNORECASE)
EXPERIENCE_RE = re.compile(r"\b(\d{1,2})\+?\s*(?:years?|yrs?)\b", re.IGNORECASE)


def _normalize_text(text: str) -> str:
    text = str(text or "")
    return re.sub(r"\s+", " ", text).strip()


def _searchable_text(text: str) -> str:
    normalized = _normalize_text(text).lower()
    return f" {normalized} "


def _alias_matches(searchable: str, alias: str) -> bool:
    alias = alias.strip().lower()
    if not alias:
        return False
    if alias.startswith(" ") or alias.endswith(" "):
        return alias in searchable
    return re.search(rf"(?<![a-z0-9+#.]){re.escape(alias)}(?![a-z0-9+#.])", searchable) is not None


def extract_skills_fallback(text: str) -> List[str]:
    """Extract known skills from resume text using local keyword rules."""
    searchable = _searchable_text(text)
    found = [
        skill
        for skill, aliases in SKILL_ALIASES.items()
        if any(_alias_matches(searchable, alias) for alias in aliases)
    ]
    logger.info("Local skill extraction found %s skills", len(found))
    return found


def _extract_name(text: str) -> str:
    label_match = NAME_LABEL_RE.search(text or "")
    if label_match:
        return label_match.group(1).strip(" .-")

    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    for line in lines[:6]:
        if EMAIL_RE.search(line) or any(char.isdigit() for char in line):
            continue
        words = re.findall(r"[A-Z][A-Za-z'-]+", line)
        if 2 <= len(words) <= 4 and len(" ".join(words)) <= 80:
            return " ".join(words)

    return "Unknown"


def _extract_education(text: str) -> str:
    for pattern in EDUCATION_PATTERNS:
        match = re.search(pattern, text or "", re.IGNORECASE)
        if match:
            return _normalize_text(match.group(0)).title()
    return "Not specified"


def _extract_years_of_experience(text: str) -> int:
    explicit_years = [int(match.group(1)) for match in EXPERIENCE_RE.finditer(text or "")]
    if explicit_years:
        return max(explicit_years)

    year_ranges = YEAR_RANGE_RE.findall(text or "")
    if year_ranges:
        return min(len(year_ranges) * 2, 15)

    return 0


def _extract_roles(text: str) -> List[str]:
    searchable = _searchable_text(text)
    roles = [
        role
        for role, aliases in ROLE_KEYWORDS.items()
        if any(_alias_matches(searchable, alias) for alias in aliases)
    ]
    return roles[:5]


def _normalize_extracted_data(data: Dict[str, Any]) -> Dict[str, Any]:
    skills = data.get("skills", [])
    if not isinstance(skills, list):
        skills = [skills] if skills else []

    clean_skills = []
    seen = set()
    for skill in skills:
        skill_text = str(skill).strip()
        if skill_text and skill_text.lower() not in seen:
            clean_skills.append(skill_text)
            seen.add(skill_text.lower())

    roles = data.get("roles", [])
    if not isinstance(roles, list):
        roles = [roles] if roles else []

    try:
        years = int(data.get("years_of_experience", 0) or 0)
    except (TypeError, ValueError):
        years = 0

    return {
        "name": str(data.get("name") or "Unknown").strip() or "Unknown",
        "skills": clean_skills,
        "years_of_experience": max(0, years),
        "education": str(data.get("education") or "Not specified").strip() or "Not specified",
        "roles": [str(role).strip() for role in roles if str(role).strip()],
        "raw_response": data.get("raw_response", {"source": "local_rules"}),
    }


def extract_skills_with_gemini(resume_text: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Backward-compatible local replacement for the old Gemini extractor.

    The timeout argument is accepted for callers that still pass it, but there is
    no external request to time out.
    """
    del timeout
    if not resume_text or not str(resume_text).strip():
        return {
            "name": "Unknown",
            "skills": [],
            "years_of_experience": 0,
            "education": "Not specified",
            "roles": [],
            "raw_response": {"source": "local_rules"},
            "error": "Empty resume text",
        }

    data = {
        "name": _extract_name(resume_text),
        "skills": extract_skills_fallback(resume_text),
        "years_of_experience": _extract_years_of_experience(resume_text),
        "education": _extract_education(resume_text),
        "roles": _extract_roles(resume_text),
        "raw_response": {"source": "local_rules"},
    }
    return _normalize_extracted_data(data)


def get_final_skills(text: str) -> List[str]:
    """Return a deduplicated skill list with sensible defaults."""
    extracted = extract_skills_with_gemini(text)
    skills = extracted.get("skills", []) if isinstance(extracted, dict) else []
    seen = {str(skill).strip().lower() for skill in skills if str(skill).strip()}
    final_skills = [str(skill).strip() for skill in skills if str(skill).strip()]

    for default_skill in ("Software Development", "Problem Solving", "Communication"):
        if len(final_skills) >= 3:
            break
        if default_skill.lower() not in seen:
            final_skills.append(default_skill)
            seen.add(default_skill.lower())

    logger.info("Final local skills: %s", final_skills)
    return final_skills


def extract_skills_safe(resume_text: str, timeout: int = 30) -> Dict[str, Any]:
    del timeout
    return {"skills": get_final_skills(resume_text)}


def _fallback_market_insights(skills: List[str]) -> List[str]:
    normalized = {str(skill).strip().lower() for skill in (skills or []) if str(skill).strip()}
    insights = []

    if {"python", "django", "fastapi", "flask"} & normalized:
        insights.append("Python backend roles are a strong target when paired with database and API project work.")
    if {"react", "javascript", "typescript", "node.js", "full stack"} & normalized:
        insights.append("Full stack roles fit candidates who can show polished UI work plus backend integration.")
    if {"machine learning", "deep learning", "artificial intelligence", "pandas", "numpy"} & normalized:
        insights.append("AI and data roles are strongest when the resume shows deployed projects and measurable outcomes.")
    if {"cybersecurity", "network security", "ethical hacking", "penetration testing"} & normalized:
        insights.append("Security roles value practical labs, incident analysis, and clear knowledge of network fundamentals.")
    if {"docker", "kubernetes", "aws", "azure", "gcp", "jenkins"} & normalized:
        insights.append("Cloud and DevOps skills improve fit for teams that need deployment and operations ownership.")

    if not insights:
        insights = [
            "Employers prioritize resumes that connect skills to practical project outcomes.",
            "Backend, data, cloud, and security paths remain reliable targets for technical candidates.",
            "A focused portfolio with two or three strong projects can improve interview conversion.",
        ]

    return insights[:5]


def get_market_insights(skills: List[str], timeout: int = 20) -> Dict[str, Any]:
    del timeout
    return {"market_insights": _fallback_market_insights(skills)}


def _skill_matches(candidate_skill: str, required_skill: str) -> bool:
    candidate = str(candidate_skill or "").strip().lower()
    required = str(required_skill or "").strip().lower()
    if not candidate or not required:
        return False
    return candidate == required or candidate in required or required in candidate


def _fallback_skill_gap(resume_skills: List[str], required_skills: List[str]) -> List[str]:
    missing = []
    for required in required_skills or []:
        if not any(_skill_matches(skill, required) for skill in resume_skills or []):
            missing.append(str(required).strip())

    gap_items = [f"Learn {skill}" for skill in missing if skill][:3]
    for fallback in (
        "Improve system design fundamentals",
        "Build one production-ready project for the target role",
        "Practice deployment and troubleshooting workflows",
    ):
        if len(gap_items) >= 3:
            break
        if fallback not in gap_items:
            gap_items.append(fallback)

    return gap_items[:5]


def get_skill_gap_for_featured_job(
    resume_skills: List[str],
    target_job_title: str,
    target_required_skills: List[str] | None = None,
    timeout: int = 20,
) -> Dict[str, Any]:
    del timeout
    required_skills = target_required_skills or []

    if not required_skills and target_job_title:
        title = str(target_job_title).lower()
        if "backend" in title:
            required_skills = ["Python", "SQL", "REST API"]
        elif "full stack" in title:
            required_skills = ["JavaScript", "React", "SQL"]
        elif "data" in title:
            required_skills = ["SQL", "Python", "Pandas"]
        elif "security" in title or "cyber" in title:
            required_skills = ["Cybersecurity", "Network Security", "Linux"]

    return {"skill_gap": _fallback_skill_gap(resume_skills, required_skills)}


def parse_gemini_response(response_text: str) -> Dict[str, Any]:
    """Compatibility parser for older callers; no Gemini call is made here."""
    skills = extract_skills_fallback(response_text or "")
    return _normalize_extracted_data(
        {
            "name": "Unknown",
            "skills": skills,
            "years_of_experience": _extract_years_of_experience(response_text or ""),
            "education": _extract_education(response_text or ""),
            "roles": _extract_roles(response_text or ""),
            "raw_response": {"source": "local_parser"},
        }
    )


def extract_skill_gaps(resume_skills: List[str], required_skills: List[str]) -> Dict[str, Any]:
    matching_skills = [
        required
        for required in required_skills or []
        if any(_skill_matches(skill, required) for skill in resume_skills or [])
    ]
    missing_skills = [
        required
        for required in required_skills or []
        if not any(_skill_matches(skill, required) for skill in resume_skills or [])
    ]
    gap_percentage = (len(missing_skills) / len(required_skills) * 100.0) if required_skills else 0.0

    return {
        "matching_skills": matching_skills,
        "missing_skills": missing_skills,
        "gap_percentage": round(gap_percentage, 2),
        "recommendations": _fallback_skill_gap(resume_skills, missing_skills),
    }


def configure_gemini() -> bool:
    """Deprecated compatibility hook. The project now runs without Gemini."""
    logger.info("External Gemini API is disabled; using local written-code extraction.")
    return True


_gemini_ready = True
