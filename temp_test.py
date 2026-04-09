from django.test.client import Client
from django.contrib.auth.models import User
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resume_ai_project.settings')
django.setup()

# Create a test user
user, created = User.objects.get_or_create(username='testuser')

# Create a client
client = Client()

# Login the user
client.force_login(user)

# Open the resume file
resume_path = r'C:\Job Reco System\Resume file\resume.pdf'
if os.path.exists(resume_path):
    with open(resume_path, 'rb') as f:
        response = client.post('/resumes/phase3/safe-extract/', {'file': f})
    
    print("\n=== RESPONSE STATUS ===")
    print(f"Status Code: {response.status_code}")
    
    print("\n=== RESPONSE DATA ===")
    try:
        data = response.json()
        print(f"Skill Count: {data.get('skill_count', 'N/A')}")
        if 'skills' in data:
            print(f"Skills List: {data['skills']}")
        if 'source' in data:
            print(f"Source: {data['source']}")
        print(f"\nFull Response: {data}")
    except:
        print(f"Response: {response.content[:500]}")
else:
    print(f"Resume file not found at {resume_path}")
