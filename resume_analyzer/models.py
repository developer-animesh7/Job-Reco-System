from django.db import models
from django.conf import settings

from resume_analyzer.security import secure_resume_upload_path


class Resume(models.Model):
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="resumes",
	)
	file = models.FileField(upload_to=secure_resume_upload_path)
	uploaded_at = models.DateTimeField(auto_now_add=True)
	extracted_text = models.TextField(null=True, blank=True)

	class Meta:
		ordering = ["-uploaded_at"]

	def __str__(self):
		return f"Resume #{self.pk} - {self.user}"
