from __future__ import annotations

from typing import Any

from job_recommendation.recommender import build_apply_links, build_featured_job
from resume_analyzer.models import Resume
from resume_analyzer.security import validate_resume_upload
from resume_analyzer.views import (
    _extract_safe_skills_from_resume,
    _finalize_response_payload,
    _save_recommendations,
    get_market_insights,
    get_job_profile_by_title,
    get_skill_gap_for_featured_job,
)


class ResumeProcessingError(Exception):
    pass


def _build_analysis_text(payload: dict[str, Any]) -> str:
    skills = payload.get("skills") or []
    featured = payload.get("featured_job") or {}
    insights = payload.get("market_insights") or []

    if skills and featured.get("title"):
        return (
            f"This resume shows strengths in {', '.join(skills[:8])}. "
            f"The strongest current match is {featured['title']} with "
            f"{featured.get('confidence', 0)}% confidence."
        )

    if insights:
        return str(insights[0])

    return "This resume has been analyzed and matched against the current job recommendation engine."


def _legacy_role_cards(payload: dict[str, Any]) -> list[dict[str, str]]:
    role_cards = []
    seen = set()

    for item in payload.get("recommendations") or []:
        title = str(item.get("job") or item.get("title") or "").strip()
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        links = build_apply_links(title)
        role_cards.append(
            {
                "title": title,
                "linkedin_link": links["linkedin"],
                "naukri_link": links["naukri"],
            }
        )

    featured = payload.get("featured_job") or {}
    featured_title = str(featured.get("title") or "").strip()
    if featured_title and featured_title.lower() not in seen:
        links = featured.get("apply_links") or build_apply_links(featured_title)
        role_cards.insert(
            0,
            {
                "title": featured_title,
                "linkedin_link": links.get("linkedin", build_apply_links(featured_title)["linkedin"]),
                "naukri_link": links.get("naukri", build_apply_links(featured_title)["naukri"]),
            },
        )

    return role_cards[:5]


def analyze_resume(uploaded_file, user) -> dict[str, Any]:
    validation_error = validate_resume_upload(uploaded_file)
    if validation_error:
        raise ResumeProcessingError(validation_error)

    resume = Resume.objects.create(user=user, file=uploaded_file)
    extraction = _extract_safe_skills_from_resume(resume)
    skills = extraction.get("skills", [])
    recommendations = _save_recommendations(resume, skills)
    featured_job = build_featured_job(recommendations)
    insights_payload = get_market_insights(skills)
    featured_profile = get_job_profile_by_title(featured_job.get("title", ""))
    skill_gap_payload = get_skill_gap_for_featured_job(
        skills,
        featured_job.get("title", ""),
        featured_profile.get("required_skills", []),
    )

    return _finalize_response_payload(
        skills,
        recommendations,
        featured_job=featured_job,
        market_insights=insights_payload.get("market_insights", []),
        skill_gap=skill_gap_payload.get("skill_gap", []),
    )


def process_resume(uploaded_file, user) -> dict[str, Any]:
    payload = analyze_resume(uploaded_file, user)
    return {
        "resume_filename": uploaded_file.name,
        "analysis_text": _build_analysis_text(payload),
        "roles": _legacy_role_cards(payload),
        "current_payload": payload,
    }
