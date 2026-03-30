from django.db import models


class Job(models.Model):
	title = models.CharField(max_length=255)
	description = models.TextField()
	skills_required = models.JSONField(default=list, blank=True)

	class Meta:
		ordering = ["title"]

	def __str__(self):
		return self.title


class Recommendation(models.Model):
	resume = models.ForeignKey(
		"resume_analyzer.Resume",
		on_delete=models.CASCADE,
		related_name="recommendations",
	)
	job = models.ForeignKey(
		Job,
		on_delete=models.CASCADE,
		related_name="recommendations",
	)
	score = models.FloatField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-score", "-created_at"]
		unique_together = ("resume", "job")

	def __str__(self):
		return f"{self.resume} -> {self.job} ({self.score:.2f})"
