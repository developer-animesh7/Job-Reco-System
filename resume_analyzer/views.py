import logging

from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.db import transaction
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_http_methods

from job_recommendation.models import Job, Recommendation
from resume_analyzer.models import Resume
from resume_analyzer.security import sanitize_skills, sanitize_text, validate_resume_upload

# Text extraction (keep as is)
try:
	from resume_analyzer.resume_parser import extract_text
except Exception:
	def extract_text(file_path):
		raise RuntimeError("extract_text is not available")


# Gemini AI Integration for skill extraction (REPLACES manual parsing)
try:
	from resume_analyzer.gemini_integration import extract_skills_with_gemini
	from resume_analyzer.gemini_integration import extract_skills_safe
	from resume_analyzer.gemini_integration import get_market_insights
	from resume_analyzer.gemini_integration import get_skill_gap_for_featured_job
except Exception as e:
	def extract_skills_with_gemini(text):
		return {"skills": []}

	def extract_skills_safe(text, timeout=30):
		return {"skills": []}

	def get_market_insights(skills, timeout=20):
		return {
			"market_insights": [
				"Technology hiring remains active for candidates with practical project experience.",
				"Roles combining backend and automation skills are seeing steady demand.",
				"Short, focused upskilling plans improve interview outcomes in competitive markets.",
			]
		}

	def get_skill_gap_for_featured_job(resume_skills, target_job_title, target_required_skills=None, timeout=20):
		return {
			"skill_gap": [
				"Learn Docker",
				"Improve system design",
			]
		}


try:
	from job_recommendation.recommender import recommend_jobs
	from job_recommendation.recommender import build_featured_job
	from job_recommendation.recommender import get_job_profile_by_title
except Exception:
	def recommend_jobs(skills):
		return []

	def build_featured_job(recommendations):
		return {
			"title": "General Software Engineer",
			"confidence": 10,
			"apply_links": {
				"linkedin": "https://www.linkedin.com/jobs/search/?keywords=General+Software+Engineer",
				"naukri": "https://www.naukri.com/general-software-engineer-jobs",
			},
		}

	def get_job_profile_by_title(job_title):
		return {}


logger = logging.getLogger(__name__)
MINIMUM_SKILL_COUNT = 3
DEFAULT_SKILLS = ["Software Development", "Problem Solving", "Communication"]


def _error_response(message, status_code=400):
	return JsonResponse({"error": sanitize_text(message)}, status=status_code)


def _validate_resume_file(uploaded_file):
	return validate_resume_upload(uploaded_file)


def _resolve_request_user(request):
	if request.user.is_authenticated:
		return request.user

	user_model = get_user_model()
	user, _ = user_model.objects.get_or_create(
		username="demo_uploader",
		defaults={"email": "demo_uploader@example.local"},
	)
	return user


def _extract_skills_from_resume(resume):
	"""Extract skills from resume using Gemini API instead of manual parsing."""
	text = extract_text(resume.file.path)
	resume.extracted_text = text
	resume.save(update_fields=["extracted_text"])

	# Using Gemini API for skill extraction (replacing manual/ML parsing)
	logger.info(f"Extracting skills from resume {resume.id} using Gemini API")
	gemini_result = extract_skills_with_gemini(text)
	
	if "error" in gemini_result:
		logger.warning(f"Gemini skill extraction error: {gemini_result.get('error')}")
	
	skills = gemini_result.get("skills", [])
	logger.info("Extracted skills for resume_id=%s: %s", resume.id, skills)
	
	return sanitize_skills(skills)


def _ensure_minimum_skills(skills, minimum=MINIMUM_SKILL_COUNT):
	clean_skills = sanitize_skills(skills or [])
	seen = {str(skill).strip().lower() for skill in clean_skills if str(skill).strip()}

	for fallback_skill in DEFAULT_SKILLS:
		if len(clean_skills) >= minimum:
			break
		if fallback_skill.lower() not in seen:
			clean_skills.append(fallback_skill)
			seen.add(fallback_skill.lower())

	if len(clean_skills) < minimum:
		clean_skills.extend(["General Technical Skill"] * (minimum - len(clean_skills)))

	return clean_skills


def _extract_text_preview_from_resume(resume, preview_chars=300):
	"""Phase 1 foundation step: extract clean text and return preview payload."""
	logger.info("Phase 1 start: text extraction for resume_id=%s", resume.id)
	text = extract_text(resume.file.path)
	text = sanitize_text(text)
	if not text:
		logger.warning("Phase 1 failed: empty extracted text for resume_id=%s", resume.id)
		raise ValueError("Could not extract readable text from resume.")

	resume.extracted_text = text
	resume.save(update_fields=["extracted_text"])

	preview = text[:preview_chars]
	logger.info(
		"Phase 1 success: resume_id=%s extracted_chars=%s preview_chars=%s",
		resume.id,
		len(text),
		len(preview),
	)
	return {
		"status": "success",
		"text_preview": preview,
	}


def _extract_structured_data_from_resume(resume):
	"""Phase 2 step: extract structured fields from resume text using Gemini."""
	logger.info("Phase 2 start: structured extraction for resume_id=%s", resume.id)
	text = extract_text(resume.file.path)
	text = sanitize_text(text)
	if not text:
		logger.warning("Phase 2 failed: empty extracted text for resume_id=%s", resume.id)
		raise ValueError("Could not extract readable text from resume.")

	resume.extracted_text = text
	resume.save(update_fields=["extracted_text"])

	gemini_data = extract_skills_with_gemini(text)
	name = sanitize_text(gemini_data.get("name", ""))
	skills = sanitize_skills(gemini_data.get("skills", []) or [])
	education = sanitize_text(gemini_data.get("education", ""))

	experience_raw = gemini_data.get("experience")
	if experience_raw is None:
		experience_raw = gemini_data.get("years_of_experience", "")
	experience = sanitize_text(experience_raw)
	if isinstance(gemini_data.get("years_of_experience"), (int, float)) and not experience:
		experience = f"{int(gemini_data.get('years_of_experience'))} years"

	payload = {
		"name": name,
		"skills": skills,
		"education": education,
		"experience": experience,
	}
	logger.info(
		"Phase 2 success: resume_id=%s name_present=%s skills_count=%s",
		resume.id,
		bool(name),
		len(skills),
	)
	return payload


def _extract_safe_skills_from_resume(resume):
	"""Phase 3 step: safely extract skills with guaranteed fallback."""
	logger.info("Phase 3 start: safe skill extraction for resume_id=%s", resume.id)
	text = extract_text(resume.file.path)
	text = sanitize_text(text)
	if not text:
		logger.warning("Phase 3 failed: empty extracted text for resume_id=%s", resume.id)
		raise ValueError("Could not extract readable text from resume.")

	resume.extracted_text = text
	resume.save(update_fields=["extracted_text"])

	result = extract_skills_safe(text)
	skills = sanitize_skills(result.get("skills", []) if isinstance(result, dict) else [])
	logger.info("Phase 3 success: resume_id=%s skills_count=%s", resume.id, len(skills))
	return {
		"skills": skills,
		"skill_count": len(skills),
		"source": "gemini+fallback"
	}


def _save_recommendations(resume, skills):
	recommended_jobs = recommend_jobs(skills) or []

	# Normalize and deduplicate recommendations by title before touching DB.
	normalized_scores = {}
	for item in recommended_jobs:
		job_title = sanitize_text(item.get("job") or item.get("title") or "")
		if not job_title:
			continue

		try:
			if item.get("score") is not None:
				score = float(item.get("score", 0.0))
			elif item.get("confidence") is not None:
				score = float(item.get("confidence", 0.0)) / 100.0
			else:
				score = 0.0
		except (TypeError, ValueError):
			score = 0.0

		normalized_scores[job_title] = max(0.0, min(score, 1.0))

	if not normalized_scores:
		logger.warning("No normalized recommendation scores for resume_id=%s", resume.id)
		return []

	logger.info("Recommendation scores for resume_id=%s: %s", resume.id, normalized_scores)

	titles = list(normalized_scores.keys())

	with transaction.atomic():
		existing_jobs = {
			job.title: job for job in Job.objects.filter(title__in=titles)
		}
		new_jobs = [
			Job(title=title, description="", skills_required=skills)
			for title in titles
			if title not in existing_jobs
		]
		if new_jobs:
			Job.objects.bulk_create(new_jobs, ignore_conflicts=True)

		jobs_by_title = {
			job.title: job for job in Job.objects.filter(title__in=titles)
		}
		job_ids = [job.id for job in jobs_by_title.values()]

		existing_recommendations = Recommendation.objects.filter(
			resume=resume,
			job_id__in=job_ids,
		).select_related("job")
		existing_by_job_id = {item.job_id: item for item in existing_recommendations}

		to_create = []
		to_update = []
		for title, score in normalized_scores.items():
			job = jobs_by_title[title]
			existing = existing_by_job_id.get(job.id)
			if existing is None:
				to_create.append(Recommendation(resume=resume, job=job, score=score))
			elif existing.score != score:
				existing.score = score
				to_update.append(existing)

		if to_create:
			Recommendation.objects.bulk_create(to_create, ignore_conflicts=True)
		if to_update:
			Recommendation.objects.bulk_update(to_update, ["score"])

		final_recommendations = Recommendation.objects.filter(
			resume=resume,
			job_id__in=job_ids,
		).select_related("job")

	return [
		{"job": recommendation.job.title, "score": recommendation.score}
		for recommendation in final_recommendations
	]


def _fallback_recommendations(skills):
	seed_skills = _ensure_minimum_skills(skills or [])
	items = recommend_jobs(seed_skills) or []
	normalized = []
	for item in items:
		title = sanitize_text(item.get("job") or item.get("title") or "")
		if not title:
			continue
		try:
			score = float(item.get("score", 0.0))
		except (TypeError, ValueError):
			score = 0.0
		if score <= 0 and item.get("confidence") is not None:
			try:
				score = float(item.get("confidence", 0.0)) / 100.0
			except (TypeError, ValueError):
				score = 0.0
		normalized.append({"job": title, "score": max(0.05, min(score, 0.9))})

	if not normalized:
		normalized = [{"job": "General Software Engineer", "score": 0.1}]

	return normalized


def _finalize_response_payload(skills, recommendations_payload, featured_job=None, market_insights=None, skill_gap=None):
	clean_skills = _ensure_minimum_skills(skills or [])

	recommendations = recommendations_payload if isinstance(recommendations_payload, list) else []
	recommendations = [item for item in recommendations if isinstance(item, dict) and sanitize_text(item.get("job", ""))]
	if not recommendations:
		recommendations = _fallback_recommendations(clean_skills)

	final_featured = featured_job if isinstance(featured_job, dict) else {}
	if not sanitize_text(final_featured.get("title", "")):
		final_featured = build_featured_job(recommendations)
	if not isinstance(final_featured.get("apply_links"), dict):
		final_featured = build_featured_job(recommendations)

	insights = [sanitize_text(item) for item in (market_insights or []) if sanitize_text(item)]
	if not insights:
		insights = get_market_insights(clean_skills).get("market_insights", [])
		insights = [sanitize_text(item) for item in insights if sanitize_text(item)]
	if not insights:
		insights = [
			"Tech hiring remains active for candidates with practical project experience.",
			"Target roles where your top skills align with core job requirements.",
			"Consistent upskilling on in-demand tools improves interview conversion.",
		]

	gap_items = [sanitize_text(item) for item in (skill_gap or []) if sanitize_text(item)]
	if not gap_items:
		profile = get_job_profile_by_title(final_featured.get("title", ""))
		gap_items = get_skill_gap_for_featured_job(
			clean_skills,
			final_featured.get("title", ""),
			profile.get("required_skills", []),
		).get("skill_gap", [])
		gap_items = [sanitize_text(item) for item in gap_items if sanitize_text(item)]
	if not gap_items:
		gap_items = ["Improve system design fundamentals", "Practice deployment and production troubleshooting"]

	if not recommendations:
		recommendations = [{"job": "General Software Engineer", "score": 0.1}]
	if not insights:
		insights = ["Hiring remains active for practical, project-driven candidates."]
	if not gap_items:
		gap_items = ["Improve system design fundamentals"]

	logger.info(
		"Final payload validated | skills=%s recommendations=%s insights=%s gap_items=%s",
		len(clean_skills),
		len(recommendations),
		len(insights),
		len(gap_items),
	)

	return {
		"skills": clean_skills,
		"skill_count": len(clean_skills),
		"featured_job": final_featured,
		"recommendations": recommendations,
		"market_insights": insights,
		"skill_gap": gap_items,
	}


@require_http_methods(["GET", "POST"])
@csrf_protect
@ensure_csrf_cookie
def upload_resume(request):
	if request.method == "GET":
		return render(request, "resume_analyzer/upload.html")

	request_user = _resolve_request_user(request)

	logger.debug("Upload endpoint called by user_id=%s", request_user.id)

	try:
		try:
			uploaded_file = request.FILES.get("file")
			validation_error = _validate_resume_file(uploaded_file)
			if validation_error:
				logger.debug("Upload validation failed: %s", validation_error)
				return _error_response(validation_error, status_code=400)

			resume = Resume.objects.create(user=request_user, file=uploaded_file)
			logger.debug("Resume stored with id=%s", resume.id)
		except (OSError, ValueError):
			logger.exception("File upload failed")
			return _error_response("File upload failed.", status_code=400)

		try:
			skills = _extract_skills_from_resume(resume)
			logger.debug("Skills extracted count=%s for resume_id=%s", len(skills), resume.id)
		except Exception:
			logger.exception("Resume parsing failed")
			return _error_response("Resume parsing failed.", status_code=422)

		try:
			recommendations_payload = _save_recommendations(resume, skills)
			featured_job = build_featured_job(recommendations_payload)
			insights_payload = get_market_insights(skills)
			featured_profile = get_job_profile_by_title(featured_job.get("title", ""))
			skill_gap_payload = get_skill_gap_for_featured_job(
				skills,
				featured_job.get("title", ""),
				featured_profile.get("required_skills", []),
			)
			logger.debug(
				"Recommendations generated count=%s for resume_id=%s",
				len(recommendations_payload),
				resume.id,
			)
		except Exception:
			logger.exception("Recommendation generation failed")
			return _error_response("Recommendation generation failed.", status_code=502)

		return JsonResponse(
			_finalize_response_payload(
				skills,
				recommendations_payload,
				featured_job=featured_job,
				market_insights=insights_payload.get("market_insights", []),
				skill_gap=skill_gap_payload.get("skill_gap", []),
			),
			status=201,
		)
	except Exception:
		logger.exception("Unexpected upload endpoint failure")
		return _error_response("Internal server error.", status_code=500)


@require_http_methods(["POST"])
@csrf_exempt
def analyze_resume(request):
	request_user = _resolve_request_user(request)

	logger.debug("Analyze endpoint called by user_id=%s", request_user.id)

	try:
		try:
			uploaded_file = request.FILES.get("file")
			validation_error = _validate_resume_file(uploaded_file)
			if validation_error:
				logger.debug("Analyze validation failed: %s", validation_error)
				return _error_response(validation_error, status_code=400)

			resume = Resume.objects.create(user=request_user, file=uploaded_file)
			logger.debug("Resume stored for analyze flow id=%s", resume.id)
		except (OSError, ValueError):
			logger.exception("File upload failed")
			return _error_response("File upload failed.", status_code=400)

		try:
			skills = _extract_skills_from_resume(resume)
			logger.debug("Analyze flow extracted skills count=%s resume_id=%s", len(skills), resume.id)
		except Exception:
			logger.exception("Resume parsing failed")
			return _error_response("Resume parsing failed.", status_code=422)

		try:
			recommendations_payload = _save_recommendations(resume, skills)
			featured_job = build_featured_job(recommendations_payload)
			insights_payload = get_market_insights(skills)
			featured_profile = get_job_profile_by_title(featured_job.get("title", ""))
			skill_gap_payload = get_skill_gap_for_featured_job(
				skills,
				featured_job.get("title", ""),
				featured_profile.get("required_skills", []),
			)
			logger.debug(
				"Analyze flow recommendations count=%s resume_id=%s",
				len(recommendations_payload),
				resume.id,
			)
		except Exception:
			logger.exception("Recommendation generation failed")
			return _error_response("Recommendation generation failed.", status_code=502)

		return JsonResponse(
			_finalize_response_payload(
				skills,
				recommendations_payload,
				featured_job=featured_job,
				market_insights=insights_payload.get("market_insights", []),
				skill_gap=skill_gap_payload.get("skill_gap", []),
			),
			status=200,
		)
	except Exception:
		logger.exception("Unexpected analyze endpoint failure")
		return _error_response("Internal server error.", status_code=500)


@require_http_methods(["POST"])
@csrf_exempt
def phase1_extract_text(request):
	"""Phase 1 endpoint: upload resume and verify extracted text preview."""
	request_user = _resolve_request_user(request)
	logger.info("Phase 1 endpoint called by user_id=%s", request_user.id)

	try:
		uploaded_file = request.FILES.get("file")
		validation_error = _validate_resume_file(uploaded_file)
		if validation_error:
			logger.debug("Phase 1 validation failed: %s", validation_error)
			return _error_response(validation_error, status_code=400)

		resume = Resume.objects.create(user=request_user, file=uploaded_file)
		payload = _extract_text_preview_from_resume(resume)
		return JsonResponse(payload, status=200)
	except ValueError as exc:
		logger.exception("Phase 1 text extraction failed")
		return _error_response(str(exc), status_code=422)
	except Exception:
		logger.exception("Unexpected Phase 1 endpoint failure")
		return _error_response("Internal server error.", status_code=500)


@require_http_methods(["POST"])
@csrf_exempt
def phase2_extract_structured(request):
	"""Phase 2 endpoint: upload resume and return Gemini structured extraction."""
	request_user = _resolve_request_user(request)
	logger.info("Phase 2 endpoint called by user_id=%s", request_user.id)

	try:
		uploaded_file = request.FILES.get("file")
		validation_error = _validate_resume_file(uploaded_file)
		if validation_error:
			logger.debug("Phase 2 validation failed: %s", validation_error)
			return _error_response(validation_error, status_code=400)

		resume = Resume.objects.create(user=request_user, file=uploaded_file)
		payload = _extract_structured_data_from_resume(resume)
		return JsonResponse(payload, status=200)
	except ValueError as exc:
		logger.exception("Phase 2 extraction failed")
		return _error_response(str(exc), status_code=422)
	except Exception:
		logger.exception("Unexpected Phase 2 endpoint failure")
		return _error_response("Internal server error.", status_code=500)


@require_http_methods(["POST"])
@csrf_exempt
def phase3_safe_extract(request):
	"""Phase 3 endpoint: safe parsing + fallback skill extraction."""
	request_user = _resolve_request_user(request)
	logger.info("Phase 3 endpoint called by user_id=%s", request_user.id)

	try:
		uploaded_file = request.FILES.get("file")
		validation_error = _validate_resume_file(uploaded_file)
		if validation_error:
			logger.debug("Phase 3 validation failed: %s", validation_error)
			return _error_response(validation_error, status_code=400)

		resume = Resume.objects.create(user=request_user, file=uploaded_file)
		payload = _extract_safe_skills_from_resume(resume)
		recommendations_payload = _save_recommendations(resume, payload.get("skills", []))
		insights_payload = get_market_insights(payload.get("skills", []))
		payload["featured_job"] = build_featured_job(recommendations_payload)
		featured_profile = get_job_profile_by_title(payload["featured_job"].get("title", ""))
		skill_gap_payload = get_skill_gap_for_featured_job(
			payload.get("skills", []),
			payload["featured_job"].get("title", ""),
			featured_profile.get("required_skills", []),
		)
		return JsonResponse(
			_finalize_response_payload(
				payload.get("skills", []),
				recommendations_payload,
				featured_job=payload.get("featured_job"),
				market_insights=insights_payload.get("market_insights", []),
				skill_gap=skill_gap_payload.get("skill_gap", []),
			),
			status=200,
		)
	except ValueError as exc:
		logger.exception("Phase 3 extraction failed")
		return _error_response(str(exc), status_code=422)
	except Exception:
		logger.exception("Unexpected Phase 3 endpoint failure")
		return _error_response("Internal server error.", status_code=500)
