AI Resume Analyzer and Job Recommendation Backend

Overview
This is a Django backend project that accepts resume uploads, extracts text and skills, generates job recommendations, stores results in the database, and returns JSON responses.

Current capabilities
- Secure resume upload validation (PDF and DOCX)
- Resume text extraction pipeline integration point
- Skill extraction pipeline integration point
- Job recommendation pipeline integration point
- Database persistence for resumes, jobs, and recommendations
- Error-safe API responses
- Automated tests for key backend scenarios

Project structure
- manage.py: Django management entry point
- resume_ai_project/settings.py: Project settings
- resume_ai_project/urls.py: Root routes
- resume_analyzer/: Upload, analysis, security checks, tests
- job_recommendation/: Job and recommendation models
- users/: User app scaffold
- PERFORMANCE.md: Performance and ORM optimization notes

Prerequisites
- Python 3.10+ (3.11 recommended)
- pip

Quick setup (Windows PowerShell)
1. Go to project folder:
   cd C:\Job Reco System\resume_ai_project

2. Create virtual environment (if not already created):
   python -m venv .venv

3. Activate virtual environment:
   .\.venv\Scripts\Activate.ps1

4. Install dependencies:
   pip install django

5. Run migrations:
   python manage.py migrate

6. Create admin user (optional but recommended):
   python manage.py createsuperuser

7. Start server:
   python manage.py runserver

8. Open in browser:
   http://127.0.0.1:8000/admin/

API endpoints
- POST /analyze-resume/
  Input: multipart form-data with file
  Output: JSON with skills and recommendations

- GET or POST /resumes/upload/
  GET: minimal upload form
  POST: upload and process resume

- POST /resumes/analyze-resume/
  Same analysis flow under app route

Request and response
Request
- Content type: multipart/form-data
- Field: file

Success response example
{
  "skills": ["Python", "Django", "SQL"],
  "recommendations": [
    {"job": "Python Developer", "score": 0.9}
  ]
}

Error response example
{
  "error": "Invalid file type. Only PDF and DOCX are allowed."
}

Validation and security notes
- Only PDF and DOCX are accepted
- File size is limited to 5 MB
- Signature-based file validation is applied
- CSRF protection is enabled for POST endpoints
- Uploaded files are stored with randomized names under media/resumes/

How to manually test quickly
Option A: Browser form
1. Log in via admin panel.
2. Open http://127.0.0.1:8000/resumes/upload/
3. Upload a PDF or DOCX file.
4. Check JSON response in browser.

Option B: API client (Postman)
1. Log in first to establish session and CSRF.
2. Send POST request to /analyze-resume/
3. Body type: form-data
4. Add key file with a valid PDF or DOCX

Run tests
- Run all resume analyzer tests:
  python manage.py test resume_analyzer -v 2

Expected tested scenarios
- Valid resume upload
- Invalid file type
- Empty file
- No skills detected
- No job matches

External integration points
This project assumes these external functions are available in your integration modules:
- extract_text(file_path)
- extract_skills(text)
- recommend_jobs(skills)

If these integrations are not connected yet, wire them in resume_analyzer/views.py import sections.

Troubleshooting
- Error: Authentication required
  Log in first (admin or session auth).

- Error: CSRF verification failed
  Use browser form or include valid CSRF token in API client.

- Error: Invalid file format
  Ensure file is real PDF or DOCX, not only renamed extension.

- Parsing or recommendation errors
  Check console logs for debug and exception messages.

Submission checklist
- Migrations applied
- Server starts without errors
- Endpoint returns expected JSON
- Tests pass
- External parser and recommender wired for your environment
