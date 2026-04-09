from django.test import TestCase

from job_recommendation.models import Job
from job_recommendation.recommender import build_apply_links, build_featured_job, recommend_jobs, strict_match


class RecommendJobsTests(TestCase):
	def test_recommend_jobs_scores_by_weighted_matching(self):
		Job.objects.create(
			title="Python Backend Developer",
			description="Backend role",
			skills_required=["Python", "Django", "SQL"],
		)
		Job.objects.create(
			title="Data Analyst",
			description="Analytics role",
			skills_required=["SQL", "Pandas", "Tableau"],
		)

		recommendations = recommend_jobs(["Python", "Django", "SQL"])

		self.assertGreaterEqual(len(recommendations), 2)
		self.assertEqual(recommendations[0]["title"], "Python Backend Developer")
		self.assertEqual(recommendations[0]["job"], "Python Backend Developer")
		self.assertIn("confidence", recommendations[0])
		self.assertIn("score", recommendations[0])
		self.assertGreater(recommendations[0]["score"], recommendations[1]["score"])

		# Ensure we are not returning identical flat scores.
		unique_scores = {item["score"] for item in recommendations}
		self.assertGreater(len(unique_scores), 1)

	def test_recommend_jobs_never_returns_empty_for_no_skills(self):
		recommendations = recommend_jobs([])
		self.assertGreaterEqual(len(recommendations), 1)
		self.assertIn("title", recommendations[0])
		self.assertIn("confidence", recommendations[0])
		self.assertIn("score", recommendations[0])

	def test_strict_match_blocks_single_char_false_positive(self):
		self.assertFalse(strict_match("C", "Security"))
		self.assertTrue(strict_match("Machine Learning", "Machine Learning"))

	def test_expected_behavior_for_c_python_ml(self):
		recommendations = recommend_jobs(["C", "Python", "Machine Learning"])
		titles = [item["title"] for item in recommendations]

		self.assertIn("AI Engineer", titles)
		self.assertIn("Backend Engineer", titles)
		self.assertNotIn("Cybersecurity Analyst", titles)

		ai = next(item for item in recommendations if item["title"] == "AI Engineer")
		backend = next(item for item in recommendations if item["title"] == "Backend Engineer")
		self.assertGreater(ai["score"], backend["score"])

	def test_general_roles_fallback_when_no_relevant_match(self):
		recommendations = recommend_jobs(["COBOL"]) 
		self.assertEqual(recommendations[0]["title"], "General Software Roles")

	def test_build_featured_job_generates_apply_links(self):
		recommendations = recommend_jobs(["Python", "Django", "SQL"])
		featured_job = build_featured_job(recommendations)

		self.assertIn("title", featured_job)
		self.assertIn("confidence", featured_job)
		self.assertIn("apply_links", featured_job)
		self.assertIn("linkedin", featured_job["apply_links"])
		self.assertIn("naukri", featured_job["apply_links"])

		links = build_apply_links(featured_job["title"])
		self.assertTrue(links["linkedin"].startswith("https://www.linkedin.com/jobs/search/?keywords="))
		self.assertTrue(links["naukri"].startswith("https://www.naukri.com/"))
