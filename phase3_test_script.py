import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "resume_ai_project.settings")
import django
django.setup()

from django.contrib.auth.models import User
from django.test.client import Client

user, _ = User.objects.get_or_create(username="testuser")
client = Client()
client.force_login(user)

resume_path = r"C:\Job Reco System\Resume file\resume.pdf"
with open(resume_path, "rb") as f:
    response = client.post("/resumes/phase3/safe-extract/", {"file": f})

print(f"Status: {response.status_code}")
data = response.json()
print(f"Skills count: {data.get('skill_count')}")
print(f"Source: {data.get('source')}")
print(f"Skills: {data.get('skills')}")
