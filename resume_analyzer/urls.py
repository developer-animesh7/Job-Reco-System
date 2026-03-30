from django.urls import path

from resume_analyzer.views import analyze_resume, upload_resume

urlpatterns = [
    path("upload/", upload_resume, name="resume-upload"),
    path("analyze-resume/", analyze_resume, name="analyze-resume"),
]
