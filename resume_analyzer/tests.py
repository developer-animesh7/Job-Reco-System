import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from job_recommendation.models import Job, Recommendation
from resume_analyzer.models import Resume

TEST_MEDIA_ROOT = tempfile.mkdtemp()


def _pdf_file(name="resume.pdf", content=b"%PDF-1.4\n%%EOF\n"):
	return SimpleUploadedFile(name, content, content_type="application/pdf")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class AnalyzeResumeAPITests(TestCase):
	@classmethod
	def setUpTestData(cls):
		user_model = get_user_model()
		cls.user = user_model.objects.create_user(username="tester", password="pass12345")

	@classmethod
	def tearDownClass(cls):
		super().tearDownClass()
		shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

	def setUp(self):
		self.client.force_login(self.user)
		self.url = "/analyze-resume/"

	@patch("resume_analyzer.views.recommend_jobs")
	@patch("resume_analyzer.views.extract_skills_with_gemini")
	@patch("resume_analyzer.views.extract_text")
	def test_valid_resume_upload(self, mock_extract_text, mock_extract_gemini, mock_recommend_jobs):
		mock_extract_text.return_value = "Python Django SQL"
		mock_extract_gemini.return_value = {"skills": ["Python", "Django", "SQL"]}
		mock_recommend_jobs.return_value = [{"title": "Python Developer", "confidence": 90, "score": 0.9, "job": "Python Developer"}]

		response = self.client.post(self.url, {"file": _pdf_file()})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["skills"], ["Python", "Django", "SQL"])
		self.assertEqual(response.json()["skill_count"], 3)
		self.assertIn("featured_job", response.json())
		self.assertIn("market_insights", response.json())
		self.assertIn("skill_gap", response.json())
		self.assertIsInstance(response.json()["market_insights"], list)
		self.assertIsInstance(response.json()["skill_gap"], list)
		self.assertIn("apply_links", response.json()["featured_job"])
		self.assertEqual(len(response.json()["recommendations"]), 1)
		self.assertEqual(Resume.objects.count(), 1)
		self.assertEqual(Job.objects.count(), 1)
		self.assertEqual(Recommendation.objects.count(), 1)

	def test_invalid_file_type(self):
		bad_file = SimpleUploadedFile("resume.txt", b"hello", content_type="text/plain")

		response = self.client.post(self.url, {"file": bad_file})

		self.assertEqual(response.status_code, 400)
		self.assertIn("error", response.json())
		self.assertEqual(Resume.objects.count(), 0)

	def test_empty_file(self):
		empty_pdf = _pdf_file(content=b"")

		response = self.client.post(self.url, {"file": empty_pdf})

		self.assertEqual(response.status_code, 400)
		self.assertIn("error", response.json())
		self.assertEqual(Resume.objects.count(), 0)

	@patch("resume_analyzer.views.recommend_jobs")
	@patch("resume_analyzer.views.extract_skills_with_gemini")
	@patch("resume_analyzer.views.extract_text")
	def test_no_skills_detected(self, mock_extract_text, mock_extract_gemini, mock_recommend_jobs):
		mock_extract_text.return_value = "No clear technology terms"
		mock_extract_gemini.return_value = {"skills": []}
		mock_recommend_jobs.return_value = []

		response = self.client.post(self.url, {"file": _pdf_file()})

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()["skills"])
		self.assertEqual(response.json()["skill_count"], len(response.json()["skills"]))
		self.assertTrue(response.json()["recommendations"])
		self.assertIn("featured_job", response.json())
		self.assertIn("market_insights", response.json())
		self.assertIn("skill_gap", response.json())
		self.assertEqual(Resume.objects.count(), 1)
		self.assertGreaterEqual(Recommendation.objects.count(), 0)

	@patch("resume_analyzer.views.recommend_jobs")
	@patch("resume_analyzer.views.extract_skills_with_gemini")
	@patch("resume_analyzer.views.extract_text")
	def test_no_job_matches(self, mock_extract_text, mock_extract_gemini, mock_recommend_jobs):
		mock_extract_text.return_value = "Python Django"
		mock_extract_gemini.return_value = {"skills": ["Python", "Django"]}
		mock_recommend_jobs.return_value = []

		response = self.client.post(self.url, {"file": _pdf_file()})

		self.assertEqual(response.status_code, 200)
		self.assertGreaterEqual(len(response.json()["skills"]), 3)
		self.assertEqual(response.json()["skill_count"], len(response.json()["skills"]))
		self.assertIn("Python", response.json()["skills"])
		self.assertIn("Django", response.json()["skills"])
		self.assertTrue(response.json()["recommendations"])
		self.assertIn("featured_job", response.json())
		self.assertIn("market_insights", response.json())
		self.assertIn("skill_gap", response.json())
		self.assertEqual(Resume.objects.count(), 1)
		self.assertGreaterEqual(Recommendation.objects.count(), 0)

	@patch("resume_analyzer.views.recommend_jobs")
	@patch("resume_analyzer.views.extract_skills_with_gemini")
	@patch("resume_analyzer.views.extract_text")
	def test_anonymous_user_can_analyze(self, mock_extract_text, mock_extract_gemini, mock_recommend_jobs):
		self.client.logout()
		mock_extract_text.return_value = "Python Django SQL"
		mock_extract_gemini.return_value = {"skills": ["Python", "Django", "SQL"]}
		mock_recommend_jobs.return_value = [{"title": "Python Backend Developer", "confidence": 75, "score": 0.75, "job": "Python Backend Developer"}]

		response = self.client.post(self.url, {"file": _pdf_file()})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["skills"], ["Python", "Django", "SQL"])
		self.assertEqual(response.json()["skill_count"], 3)
		self.assertIn("featured_job", response.json())
		self.assertIn("market_insights", response.json())
		self.assertIn("skill_gap", response.json())
		self.assertIsInstance(response.json()["market_insights"], list)
		self.assertIsInstance(response.json()["skill_gap"], list)
		self.assertEqual(len(response.json()["recommendations"]), 1)
		self.assertEqual(Resume.objects.count(), 1)

	@patch("resume_analyzer.views.extract_text")
	def test_phase1_extract_text_success(self, mock_extract_text):
		mock_extract_text.return_value = "A" * 350

		response = self.client.post("/resumes/phase1/extract-text/", {"file": _pdf_file()})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload["status"], "success")
		self.assertEqual(len(payload["text_preview"]), 300)

	@patch("resume_analyzer.views.extract_text")
	def test_phase1_extract_text_empty_output(self, mock_extract_text):
		mock_extract_text.return_value = "   "

		response = self.client.post("/resumes/phase1/extract-text/", {"file": _pdf_file()})

		self.assertEqual(response.status_code, 422)
		self.assertIn("error", response.json())

	@patch("resume_analyzer.views.extract_skills_with_gemini")
	@patch("resume_analyzer.views.extract_text")
	def test_phase2_extract_structured_success(self, mock_extract_text, mock_extract_gemini):
		mock_extract_text.return_value = "Python Django SQL experience profile"
		mock_extract_gemini.return_value = {
			"name": "Animesh Patra",
			"skills": ["Python", "Django", "SQL"],
			"education": "B.Tech Computer Science",
			"years_of_experience": 2,
		}

		response = self.client.post("/resumes/phase2/extract-structured/", {"file": _pdf_file()})

		self.assertEqual(response.status_code, 200)
		payload = response.json()
		self.assertEqual(payload["name"], "Animesh Patra")
		self.assertEqual(payload["skills"], ["Python", "Django", "SQL"])
		self.assertEqual(payload["education"], "B.Tech Computer Science")
		self.assertEqual(payload["experience"], "2")

	@patch("resume_analyzer.views.extract_text")
	def test_phase2_extract_structured_empty_text(self, mock_extract_text):
		mock_extract_text.return_value = ""

		response = self.client.post("/resumes/phase2/extract-structured/", {"file": _pdf_file()})

		self.assertEqual(response.status_code, 422)
		self.assertIn("error", response.json())

	@patch("resume_analyzer.views.extract_skills_safe")
	@patch("resume_analyzer.views.extract_text")
	def test_phase3_safe_extract_success(self, mock_extract_text, mock_extract_safe):
		mock_extract_text.return_value = "Python Django SQL"
		mock_extract_safe.return_value = {"skills": ["Python", "Django", "SQL"]}

		response = self.client.post("/resumes/phase3/safe-extract/", {"file": _pdf_file()})

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertEqual(data["skills"], ["Python", "Django", "SQL"])
		self.assertEqual(data["skill_count"], 3)
		self.assertIn("featured_job", data)
		self.assertIn("recommendations", data)
		self.assertIn("market_insights", data)
		self.assertIn("skill_gap", data)
		self.assertIsInstance(data["market_insights"], list)
		self.assertIsInstance(data["skill_gap"], list)

	@patch("resume_analyzer.views.extract_skills_safe")
	@patch("resume_analyzer.views.extract_text")
	def test_phase3_safe_extract_handles_empty_gemini_skills(self, mock_extract_text, mock_extract_safe):
		mock_extract_text.return_value = "Worked with Python and Django APIs"
		mock_extract_safe.return_value = {"skills": ["Python", "Django"]}

		response = self.client.post("/resumes/phase3/safe-extract/", {"file": _pdf_file()})

		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertGreaterEqual(len(data["skills"]), 3)
		self.assertEqual(data["skill_count"], len(data["skills"]))
		self.assertIn("Python", data["skills"])
		self.assertIn("Django", data["skills"])
		self.assertIn("featured_job", data)
		self.assertIn("recommendations", data)
		self.assertIn("market_insights", data)
		self.assertIn("skill_gap", data)
