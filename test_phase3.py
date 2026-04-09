import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resume_ai_project.settings')
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from pathlib import Path

User = get_user_model()
user, _ = User.objects.get_or_create(username='phase3_runner', defaults={'email': 'phase3_runner@example.com'})
user.set_password('phase3_runner_pw')
user.save()

client = Client()
client.force_login(user)

resume_path = Path(r'C:\Job Reco System\Resume file\resume.pdf')
if resume_path.exists():
    resume_data = resume_path.read_bytes()
    print(f'File size: {len(resume_data)} bytes')
    
    uploaded_file = SimpleUploadedFile(
        'resume.pdf',
        resume_data,
        content_type='application/pdf'
    )
    print(f'File object: {uploaded_file.name}, size: {uploaded_file.size}')
    
    response = client.post(
        '/resumes/phase3/safe-extract/',
        {'file': uploaded_file},
        follow=True
    )
    
    print(f'status_code={response.status_code}')
    
    try:
        data = response.json()
        skills_list = data.get('skills', [])
        print(f'skills_count={len(skills_list)}')
        if response.status_code == 200:
            print('Phase 3: PASS')
        else:
            print('Phase 3: FAIL')
    except Exception as e:
        print(f'skills_count=0')
        print(f'Phase 3: FAIL - {str(e)[:50]}')
else:
    print('Resume file not found')
