from django.urls import path

from resume_analyzer.views import analyze_resume, phase1_extract_text, phase2_extract_structured, phase3_safe_extract, upload_resume

urlpatterns = [
    path("upload/", upload_resume, name="resume-upload"),
    path("analyze-resume/", analyze_resume, name="analyze-resume"),
    path("phase1/extract-text/", phase1_extract_text, name="phase1-extract-text"),
    path("phase2/extract-structured/", phase2_extract_structured, name="phase2-extract-structured"),
    path("phase3/safe-extract/", phase3_safe_extract, name="phase3-safe-extract"),
]
