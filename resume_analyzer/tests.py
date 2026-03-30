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
	@patch("resume_analyzer.views.extract_skills")
	@patch("resume_analyzer.views.extract_text")
	def test_valid_resume_upload(self, mock_extract_text, mock_extract_skills, mock_recommend_jobs):
		mock_extract_text.return_value = "Python Django SQL"
		mock_extract_skills.return_value = ["Python", "Django", "SQL"]
		mock_recommend_jobs.return_value = [{"job": "Python Developer", "score": 0.9}]

		response = self.client.post(self.url, {"file": _pdf_file()})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["skills"], ["Python", "Django", "SQL"])
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
	@patch("resume_analyzer.views.extract_skills")
	@patch("resume_analyzer.views.extract_text")
	def test_no_skills_detected(self, mock_extract_text, mock_extract_skills, mock_recommend_jobs):
		mock_extract_text.return_value = "No clear technology terms"
		mock_extract_skills.return_value = []
		mock_recommend_jobs.return_value = []

		response = self.client.post(self.url, {"file": _pdf_file()})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["skills"], [])
		self.assertEqual(response.json()["recommendations"], [])
		self.assertEqual(Resume.objects.count(), 1)
		self.assertEqual(Recommendation.objects.count(), 0)

	@patch("resume_analyzer.views.recommend_jobs")
	@patch("resume_analyzer.views.extract_skills")
	@patch("resume_analyzer.views.extract_text")
	def test_no_job_matches(self, mock_extract_text, mock_extract_skills, mock_recommend_jobs):
		mock_extract_text.return_value = "Python Django"
		mock_extract_skills.return_value = ["Python", "Django"]
		mock_recommend_jobs.return_value = []

		response = self.client.post(self.url, {"file": _pdf_file()})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["skills"], ["Python", "Django"])
		self.assertEqual(response.json()["recommendations"], [])
		self.assertEqual(Resume.objects.count(), 1)
		self.assertEqual(Recommendation.objects.count(), 0)
