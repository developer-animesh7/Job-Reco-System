import logging

from django.http import JsonResponse
from django.db import transaction
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from job_recommendation.models import Job, Recommendation
from resume_analyzer.models import Resume
from resume_analyzer.security import sanitize_skills, sanitize_text, validate_resume_upload

try:
	from resume_analyzer.resume_parser import extract_skills, extract_text
except Exception:
	# Fallback keeps upload endpoint stable when parser module is unavailable.
	def extract_text(file_path):
		raise RuntimeError("extract_text is not available")

	def extract_skills(text):
		raise RuntimeError("extract_skills is not available")


try:
	from job_recommendation.recommender import recommend_jobs
except Exception:
	def recommend_jobs(skills):
		return []


logger = logging.getLogger(__name__)


def _error_response(message, status_code=400):
	return JsonResponse({"error": sanitize_text(message)}, status=status_code)


def _validate_resume_file(uploaded_file):
	return validate_resume_upload(uploaded_file)


def _extract_skills_from_resume(resume):
	text = extract_text(resume.file.path)
	resume.extracted_text = text
	resume.save(update_fields=["extracted_text"])

	skills_result = extract_skills(text)
	if isinstance(skills_result, dict) and "skills" in skills_result:
		return sanitize_skills(skills_result.get("skills", []) or [])
	if isinstance(skills_result, list):
		return sanitize_skills(skills_result)
	return []


def _save_recommendations(resume, skills):
	recommended_jobs = recommend_jobs(skills) or []

	# Normalize and deduplicate recommendations by title before touching DB.
	normalized_scores = {}
	for item in recommended_jobs:
		job_title = sanitize_text(item.get("job", ""))
		if not job_title:
			continue

		try:
			score = float(item.get("score", 0.0))
		except (TypeError, ValueError):
			score = 0.0

		normalized_scores[job_title] = max(0.0, min(score, 1.0))

	if not normalized_scores:
		return []

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


@require_http_methods(["GET", "POST"])
@csrf_protect
def upload_resume(request):
	if request.method == "GET":
		return render(request, "resume_analyzer/upload.html")

	if not request.user.is_authenticated:
		return _error_response("Authentication required.", status_code=401)

	logger.debug("Upload endpoint called by user_id=%s", request.user.id)

	try:
		try:
			uploaded_file = request.FILES.get("file")
			validation_error = _validate_resume_file(uploaded_file)
			if validation_error:
				logger.debug("Upload validation failed: %s", validation_error)
				return _error_response(validation_error, status_code=400)

			resume = Resume.objects.create(user=request.user, file=uploaded_file)
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
			logger.debug(
				"Recommendations generated count=%s for resume_id=%s",
				len(recommendations_payload),
				resume.id,
			)
		except Exception:
			logger.exception("Recommendation generation failed")
			return _error_response("Recommendation generation failed.", status_code=502)

		return JsonResponse(
			{
				"skills": skills,
				"recommendations": recommendations_payload,
			},
			status=201,
		)
	except Exception:
		logger.exception("Unexpected upload endpoint failure")
		return _error_response("Internal server error.", status_code=500)


@require_http_methods(["POST"])
@csrf_protect
def analyze_resume(request):
	if not request.user.is_authenticated:
		return _error_response("Authentication required.", status_code=401)

	logger.debug("Analyze endpoint called by user_id=%s", request.user.id)

	try:
		try:
			uploaded_file = request.FILES.get("file")
			validation_error = _validate_resume_file(uploaded_file)
			if validation_error:
				logger.debug("Analyze validation failed: %s", validation_error)
				return _error_response(validation_error, status_code=400)

			resume = Resume.objects.create(user=request.user, file=uploaded_file)
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
			logger.debug(
				"Analyze flow recommendations count=%s resume_id=%s",
				len(recommendations_payload),
				resume.id,
			)
		except Exception:
			logger.exception("Recommendation generation failed")
			return _error_response("Recommendation generation failed.", status_code=502)

		return JsonResponse(
			{
				"skills": skills,
				"recommendations": recommendations_payload,
			},
			status=200,
		)
	except Exception:
		logger.exception("Unexpected analyze endpoint failure")
		return _error_response("Internal server error.", status_code=500)
