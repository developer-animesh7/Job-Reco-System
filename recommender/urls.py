from django.urls import path

from .views import api_analyze_resume, legacy_home


urlpatterns = [
    path("legacy/", legacy_home, name="legacy-recommender-home"),
    path("api/analyze-resume/", api_analyze_resume, name="api-analyze-resume"),
]
