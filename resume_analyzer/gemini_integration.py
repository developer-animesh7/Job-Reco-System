"""
Gemini AI Integration for Resume Skill Extraction

Replaces traditional NLP parsing with Google's Gemini API
for more accurate and structured skill extraction.
"""

import json
import logging
import os
import re
import hashlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import List, Dict, Any

try:
    from django.core.cache import cache
except Exception:
    cache = None

modern_genai = None
legacy_genai = None

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.0-flash"
_gemini_client = None
_gemini_mode = None
GEMINI_CACHE_TTL_SECONDS = int(os.getenv("GEMINI_CACHE_TTL_SECONDS", "900"))


def _build_cache_key(prefix: str, payload: str) -> str:
    digest = hashlib.sha256(payload.encode("utf-8", errors="ignore")).hexdigest()
    return f"gemini:{prefix}:{digest}"


def _cache_get(cache_key: str) -> str | None:
    if cache is None:
        return None
    try:
        return cache.get(cache_key)
    except Exception as exc:
        logger.warning("Gemini cache get failed: %s", exc)
        return None


def _cache_set(cache_key: str, value: str) -> None:
    if cache is None:
        return
    try:
        cache.set(cache_key, value, timeout=GEMINI_CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Gemini cache set failed: %s", exc)


def _run_with_timeout(callable_fn, timeout: int):
    # Hard timeout wrapper so external SDK calls cannot hang request threads.
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_fn)
        return future.result(timeout=max(1, int(timeout or 1)))


# STEP 1: COMPREHENSIVE SKILL DATABASE (50+ skills)
SKILL_DB = {
    # Programming Languages
    "python", "java", "c", "c++", "c#", "javascript", "typescript",
    "kotlin", "swift", "go", "rust", "php", "ruby", "perl", "scala",
    
    # Web Frameworks & Libraries
    "django", "flask", "fastapi", "react", "vue", "angular",
    "node.js", "express", "springboot", "asp.net", "laravel",
    
    # Databases & Storage
    "sql", "postgresql", "mysql", "mongodb", "oracle",
    "redis", "elasticsearch", "cassandra", "dynamodb", "firestore",
    
    # Cloud & DevOps
    "aws", "azure", "gcp", "docker", "kubernetes",
    "terraform", "jenkins", "gitlab ci", "github actions", "circleci",
    
    # AI/ML & Data
    "machine learning", "deep learning", "artificial intelligence",
    "nlp", "computer vision", "tensorflow", "pytorch", "keras",
    "scikit-learn", "pandas", "numpy", "matplotlib", "jupyter",
    
    # Security & Cybersecurity
    "cybersecurity", "ethical hacking", "network security",
    "security", "penetration testing", "firewall", "ssl", "encryption",
    "authentication", "authorization", "owasp",
    
    # Development Practices & Methodologies
    "full stack", "full-stack", "full-stack development",
    "web development", "software development", "android development",
    "ios development", "mobile development", "responsible development",
    "rest api", "graphql", "microservices", "agile", "scrum",
    
    # Tools & Platforms
    "git", "github", "gitlab", "bitbucket",
    "linux", "unix", "windows", "macos",
    "vim", "vscode", "intellij", "eclipse",
    "jira", "confluence", "slack",
}


def extract_skills_fallback(text: str):
    """
    STEP 2: Flexible fallback extraction with variation handling.
    
    - Convert text to lowercase
    - Match skills using substring logic
    - Handle variations (e.g., "full-stack" vs "full stack")
    - Remove duplicates
    - Return clean list
    """
    if not text or not isinstance(text, str):
        logger.warning("Fallback: empty or invalid text provided")
        return []

    text_lower = text.lower()
    found_skills = []
    seen = set()

    for skill in SKILL_DB:
        skill_lower = skill.lower()
        # Exact word boundary match with flexible spacing
        patterns = [
            r'\b' + re.escape(skill_lower) + r'\b',
            r'\b' + re.escape(skill_lower.replace(" ", "-")) + r'\b',
            r'\b' + re.escape(skill_lower.replace("-", "")) + r'\b',
        ]
        
        for pattern in patterns:
            if re.search(pattern, text_lower):
                # Convert back to proper case for display
                display_skill = skill.title()
                if display_skill.lower() not in seen:
                    found_skills.append(display_skill)
                    seen.add(display_skill.lower())
                break

    logger.info(f"Fallback extraction found {len(found_skills)} skills")
    return found_skills

KNOWN_SKILLS = {
    "python", "django", "flask", "fastapi", "javascript", "typescript", "react",
    "vue", "angular", "sql", "postgresql", "mysql", "mongodb", "redis", "docker",
    "kubernetes", "aws", "azure", "gcp", "git", "pandas", "numpy", "scikit-learn",
    "tensorflow", "pytorch", "tableau", "power bi", "airflow", "jenkins", "ci/cd",
    "html", "css", "rest api", "graphql",
}


def _fallback_extract_skills_from_text(resume_text: str) -> Dict[str, Any]:
    """Legacy wrapper for backward compatibility."""
    skills = extract_skills_fallback(resume_text)
    return {
        "name": "Unknown",
        "skills": skills,
        "years_of_experience": 0,
        "education": "Not specified",
        "roles": [],
        "raw_response": {"source": "local_fallback"},
    }


def configure_gemini():
    """
    Configure Gemini API with API key from environment or settings.
    
    Expects GEMINI_API_KEY in environment variables.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set in environment. Gemini features may not work.")
        return False
    
    global _gemini_client, _gemini_mode, modern_genai, legacy_genai

    try:
        if modern_genai is None:
            try:
                from google import genai as imported_modern_genai
                modern_genai = imported_modern_genai
            except Exception:
                modern_genai = None

        if modern_genai is not None:
            _gemini_client = modern_genai.Client(api_key=api_key)
            _gemini_mode = "modern"
            logger.info("Gemini configured with google.genai")
            return True

        if legacy_genai is None:
            try:
                import google.generativeai as imported_legacy_genai
                legacy_genai = imported_legacy_genai
            except Exception:
                legacy_genai = None

        if legacy_genai is not None:
            legacy_genai.configure(api_key=api_key)
            _gemini_mode = "legacy"
            logger.info("Gemini configured with google.generativeai")
            return True

        logger.error("No Gemini SDK available. Install google-genai or google-generativeai.")
        return False
    except Exception as e:
        logger.error(f"Failed to configure Gemini: {e}")
        return False


def _generate_gemini_text(prompt: str, timeout: int = 30, cache_prefix: str = "default") -> str:
    cache_key = _build_cache_key(cache_prefix, prompt)
    cached_text = _cache_get(cache_key)
    if isinstance(cached_text, str) and cached_text:
        logger.debug("Gemini cache hit for prefix=%s", cache_prefix)
        return cached_text

    if _gemini_mode == "modern":
        try:
            response = _run_with_timeout(
                lambda: _gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                ),
                timeout,
            )
            text = getattr(response, "text", "") or ""
            if text:
                _cache_set(cache_key, text)
            return text
        except FuturesTimeoutError as exc:
            logger.error("Gemini modern call timed out after %ss", timeout)
            raise TimeoutError(f"Gemini timeout after {timeout}s") from exc

    if _gemini_mode == "legacy":
        try:
            model = legacy_genai.GenerativeModel(GEMINI_MODEL)
            response = _run_with_timeout(
                lambda: model.generate_content(prompt, request_options={"timeout": timeout}),
                timeout,
            )
            text = getattr(response, "text", "") or ""
            if text:
                _cache_set(cache_key, text)
            return text
        except FuturesTimeoutError as exc:
            logger.error("Gemini legacy call timed out after %ss", timeout)
            raise TimeoutError(f"Gemini timeout after {timeout}s") from exc

    raise RuntimeError("Gemini is not configured")


def extract_skills_with_gemini(resume_text: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Extract skills from resume text using Gemini API.
    
    Args:
        resume_text: Plain text content of resume
        timeout: API request timeout in seconds
        
    Returns:
        Dictionary with extracted data:
        {
            "skills": ["Python", "Django", ...],
            "experience_level": "Senior",
            "name": "John Doe",
            "education": [...],
            "raw_response": "..."  # For debugging
        }
        
    Falls back to empty skills if extraction fails.
    """
    if not resume_text or not resume_text.strip():
        logger.warning("Empty resume text provided to Gemini")
        return {"skills": [], "error": "Empty resume text"}
    
    try:
        prompt = f"""
        Extract professional information from this resume. Return ONLY valid JSON.
        
        Extract:
        1. Full Name
        2. Skills (as a list of specific technical/professional skills)
        3. Years of Experience (estimate from work history)
        4. Education level
        5. Job titles/roles held
        
        Return format:
        {{
            "name": "Full Name",
            "skills": ["Skill1", "Skill2", "Skill3"],
            "years_of_experience": 5,
            "education": "Bachelor's in Computer Science",
            "roles": ["Role1", "Role2"]
        }}
        
        Resume:
        {resume_text}
        
        IMPORTANT: Return ONLY the JSON object, no additional text.
        """
        
        logger.debug("Sending resume text to Gemini for extraction")
        response_text = _generate_gemini_text(prompt, timeout=timeout, cache_prefix="skills")
        
        logger.debug("Gemini response received")
        extracted = parse_gemini_response(response_text)
        
        return extracted
        
    except Exception as e:
        logger.exception("Gemini extraction failed; using fallback")
        # Keep pipeline operational even if Gemini is unavailable (quota/network/model).
        fallback = _fallback_extract_skills_from_text(resume_text)
        fallback["error"] = f"Gemini extraction failed: {str(e)}"
        return fallback


def get_final_skills(text: str):
    """
    STEP 4: CRITICAL merge strategy.
    
    Logic:
    1. Extract from Gemini
    2. Extract fallback skills
    3. Merge and deduplicate
    4. Guarantee minimum 3 skills
    
    Returns:
    - List of unique skills (case-normalized)
    """
    if not text or not isinstance(text, str) or not text.strip():
        logger.warning("get_final_skills: empty text provided")
        return []

    # Step 1: Get Gemini skills
    gemini_data = extract_skills_with_gemini(text)
    gemini_skills = gemini_data.get("skills", []) if isinstance(gemini_data, dict) else []
    if not isinstance(gemini_skills, list):
        gemini_skills = []
    gemini_skills = [str(s).strip() for s in gemini_skills if s]

    # Step 2: Get fallback skills
    fallback_skills = extract_skills_fallback(text)

    # Step 3: Merge and deduplicate
    all_skills = gemini_skills + fallback_skills
    seen = set()
    final_skills = []
    for skill in all_skills:
        skill_lower = str(skill).lower().strip()
        if skill_lower and skill_lower not in seen:
            seen.add(skill_lower)
            final_skills.append(skill)

    # Step 4: Guarantee minimum skills
    if len(final_skills) < 3:
        logger.warning(f"Final skills count {len(final_skills)} < 3, using fallback only")
        fallback_skills = extract_skills_fallback(text)
        seen = set()
        final_skills = []
        for skill in fallback_skills:
            skill_lower = str(skill).lower().strip()
            if skill_lower and skill_lower not in seen:
                seen.add(skill_lower)
                final_skills.append(skill)

    # Step 6: LOGGING (MANDATORY)
    if len(final_skills) < 3:
        default_skills = ["Software Development", "Problem Solving", "Communication"]
        for default_skill in default_skills:
            if len(final_skills) >= 3:
                break
            if default_skill.lower() not in seen:
                final_skills.append(default_skill)
                seen.add(default_skill.lower())

    logger.info("Gemini skills extracted: %s", gemini_skills)
    logger.info("Fallback skills extracted: %s", fallback_skills)
    logger.info("Final merged skills: %s (count=%s)", final_skills, len(final_skills))

    return final_skills


def extract_skills_safe(resume_text: str, timeout: int = 30) -> Dict[str, Any]:
    """Phase 3 safe extraction: uses new get_final_skills merge strategy."""
    if not resume_text or not resume_text.strip():
        return {"skills": []}

    final_skills = get_final_skills(resume_text)
    return {"skills": final_skills}


def _fallback_market_insights(skills: List[str]) -> List[str]:
    normalized = {str(skill).strip().lower() for skill in (skills or []) if str(skill).strip()}

    insights = []
    if any("cyber" in skill or "security" in skill for skill in normalized):
        insights.append("Cybersecurity roles remain in strong demand across product and enterprise teams.")
    if any("python" in skill for skill in normalized):
        insights.append("Python backend and automation opportunities are expanding in startups and SaaS companies.")
    if any("machine learning" in skill or "artificial intelligence" in skill or "deep learning" in skill for skill in normalized):
        insights.append("AI and ML hiring is growing fastest in applied engineering roles with production skills.")
    if any("full stack" in skill or "react" in skill or "node" in skill for skill in normalized):
        insights.append("Full-stack developers with modern web frameworks are preferred for rapid product teams.")
    if any("docker" in skill or "kubernetes" in skill or "aws" in skill for skill in normalized):
        insights.append("Cloud and DevOps skills improve interview conversion for backend-focused positions.")

    if not insights:
        insights = [
            "Employers prioritize practical projects that show end-to-end problem solving.",
            "Roles that combine development and automation skills are trending in 2026.",
            "Target positions where your strongest skills map directly to required technologies.",
        ]

    return insights[:5]


def _parse_market_insights_response(response_text: str) -> List[str]:
    if not response_text:
        return []

    text = response_text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()][:5]
        if isinstance(parsed, dict):
            candidates = parsed.get("market_insights") or parsed.get("insights") or []
            if isinstance(candidates, list):
                return [str(item).strip() for item in candidates if str(item).strip()][:5]
    except Exception:
        pass

    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*\d\.)\s]+", "", line).strip()
        if line:
            lines.append(line)

    return lines[:5]


def get_market_insights(skills: List[str], timeout: int = 20) -> Dict[str, Any]:
    """
    Generate short market insights using Gemini, with safe fallback.

    Returns:
        {
            "market_insights": ["..."]
        }
    """
    clean_skills = [str(skill).strip() for skill in (skills or []) if str(skill).strip()]
    if not clean_skills:
        return {"market_insights": _fallback_market_insights([])}

    try:
        if _gemini_client is None or _gemini_mode is None:
            configure_gemini()

        prompt = f"""
Given these skills:
{', '.join(clean_skills)}

Return:
- Trending roles
- Market demand
- Career suggestions

Return 3-5 short bullet points.
Return ONLY JSON in this exact format:
{{
  "market_insights": [
    "Short point 1",
    "Short point 2",
    "Short point 3"
  ]
}}
"""

        response_text = _generate_gemini_text(prompt, timeout=timeout, cache_prefix="market-insights")
        parsed = _parse_market_insights_response(response_text)
        if parsed:
            return {"market_insights": parsed[:5]}
    except Exception as exc:
        logger.warning("Market insights Gemini fallback triggered: %s", exc)

    return {"market_insights": _fallback_market_insights(clean_skills)}


def _parse_short_bullets(response_text: str, key_name: str) -> List[str]:
    if not response_text:
        return []

    text = response_text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            values = parsed.get(key_name) or []
            if isinstance(values, list):
                return [str(item).strip() for item in values if str(item).strip()][:5]
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()][:5]
    except Exception:
        pass

    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[-*\d\.)\s]+", "", line).strip()
        if line:
            lines.append(line)
    return lines[:5]


def _fallback_skill_gap(resume_skills: List[str], required_skills: List[str]) -> List[str]:
    resume_norm = {str(skill).strip().lower() for skill in (resume_skills or []) if str(skill).strip()}
    required = [str(skill).strip() for skill in (required_skills or []) if str(skill).strip()]

    missing = []
    for req in required:
        req_norm = req.lower()
        matched = any(req_norm in r or r in req_norm for r in resume_norm)
        if not matched:
            missing.append(req)

    bullets = [f"Learn {skill}" for skill in missing[:3]]
    if len(bullets) < 3:
        bullets.append("Improve system design fundamentals")
    if len(bullets) < 3:
        bullets.append("Practice production-ready project deployment")

    return bullets[:5]


def get_skill_gap_for_featured_job(
    resume_skills: List[str],
    target_job_title: str,
    target_required_skills: List[str] | None = None,
    timeout: int = 20,
) -> Dict[str, Any]:
    """
    Return concise missing-skill bullets for the featured job.

    Output:
    {
        "skill_gap": ["Learn Docker", "Improve system design"]
    }
    """
    clean_resume_skills = [str(skill).strip() for skill in (resume_skills or []) if str(skill).strip()]
    clean_required = [str(skill).strip() for skill in (target_required_skills or []) if str(skill).strip()]
    target_title = str(target_job_title or "").strip()

    if not target_title:
        return {"skill_gap": _fallback_skill_gap(clean_resume_skills, clean_required)}

    try:
        if _gemini_client is None or _gemini_mode is None:
            configure_gemini()

        required_section = ", ".join(clean_required) if clean_required else "Not provided"
        prompt = f"""
For this resume and target job, suggest missing skills.

Resume skills: {', '.join(clean_resume_skills) if clean_resume_skills else 'Not provided'}
Target job: {target_title}
Target required skills: {required_section}

Return ONLY JSON with 3-5 short bullet items:
{{
  "skill_gap": [
    "Learn Docker",
    "Improve system design"
  ]
}}
"""

        response_text = _generate_gemini_text(prompt, timeout=timeout, cache_prefix="skill-gap")
        parsed = _parse_short_bullets(response_text, "skill_gap")
        if parsed:
            return {"skill_gap": parsed[:5]}
    except Exception as exc:
        logger.warning("Skill gap Gemini fallback triggered: %s", exc)

    return {"skill_gap": _fallback_skill_gap(clean_resume_skills, clean_required)}


def parse_gemini_response(response_text: str) -> Dict[str, Any]:
    """
    Parse JSON response from Gemini, handling cases where extra text is included.
    
    Args:
        response_text: Raw text response from Gemini
        
    Returns:
        Parsed JSON dictionary or fallback with empty skills
    """
    if not response_text:
        logger.warning("Empty Gemini response")
        return {"skills": [], "error": "Empty response from Gemini"}
    
    try:
        # Try direct JSON parsing first
        try:
            data = json.loads(response_text)
            logger.debug("Successfully parsed Gemini response as JSON")
            return _normalize_gemini_data(data)
        except json.JSONDecodeError:
            # Gemini may include extra text, extract JSON block
            logger.debug("Direct JSON parsing failed, attempting to extract JSON block")
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            
            if start == -1 or end == 0:
                logger.warning("No JSON block found in Gemini response")
                return {"skills": [], "error": "Invalid response format"}
            
            json_str = response_text[start:end]
            data = json.loads(json_str)
            logger.debug("Successfully extracted and parsed JSON from response")
            return _normalize_gemini_data(data)
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Gemini response as JSON: {e}")
        return {"skills": [], "error": f"JSON parsing failed: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error parsing Gemini response: {e}")
        return {"skills": [], "error": str(e)}


def _normalize_gemini_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize Gemini response data to consistent format.
    
    Handles various field names Gemini might use and validates data.
    """
    # Extract skills, handling various possible field names
    skills = data.get("skills", [])
    if not isinstance(skills, list):
        skills = [str(skills)] if skills else []
    
    # Filter out empty/None skills and convert to strings
    skills = [str(s).strip() for s in skills if s]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_skills = []
    for skill in skills:
        if skill.lower() not in seen:
            seen.add(skill.lower())
            unique_skills.append(skill)
    
    # Get other fields
    name = data.get("name", "Unknown")
    experience = data.get("years_of_experience", 0)
    education = data.get("education", "Not specified")
    roles = data.get("roles", [])
    
    if not isinstance(roles, list):
        roles = [str(roles)] if roles else []
    
    logger.debug(f"Normalized {len(unique_skills)} skills from Gemini")
    
    return {
        "name": str(name),
        "skills": unique_skills,
        "years_of_experience": int(experience) if isinstance(experience, (int, float)) else 0,
        "education": str(education),
        "roles": [str(r) for r in roles if r],
        "raw_response": data
    }


def extract_skill_gaps(resume_skills: List[str], required_skills: List[str]) -> Dict[str, Any]:
    """
    Use Gemini to analyze skill gaps between resume and job requirements.
    
    Args:
        resume_skills: Skills found in resume
        required_skills: Skills required for target job
        
    Returns:
        Dictionary with gap analysis
    """
    if not resume_skills or not required_skills:
        return {
            "missing_skills": required_skills,
            "matching_skills": [],
            "gap_percentage": 100.0 if required_skills else 0.0
        }
    
    try:
        prompt = f"""
        Analyze skill gaps between a candidate's skills and job requirements.
        
        Resume Skills: {', '.join(resume_skills)}
        Required Skills: {', '.join(required_skills)}
        
        Return JSON:
        {{
            "matching_skills": [...],
            "missing_skills": [...],
            "gap_percentage": 0.0,
            "recommendations": ["Learn X", "Improve Y"]
        }}
        
        Return ONLY JSON.
        """
        
        response_text = _generate_gemini_text(prompt)
        data = parse_gemini_response(response_text)
        
        return data.get("raw_response", {})
        
    except Exception as e:
        logger.error(f"Skill gap analysis failed: {e}")
        return {
            "error": str(e),
            "missing_skills": required_skills,
            "matching_skills": resume_skills
        }


# Initialize Gemini on module import
_gemini_ready = configure_gemini()
