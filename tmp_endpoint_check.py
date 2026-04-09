from pathlib import Path
from django.test import Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

pdf_path = Path(r"C:\Job Reco System\Resume file\resume.pdf")
print(f"Using resume file: {pdf_path} (exists={pdf_path.exists()})")
if not pdf_path.exists():
    raise SystemExit("Resume file not found")

file_bytes = pdf_path.read_bytes()

client = Client()
User = get_user_model()
user, created = User.objects.get_or_create(username="endpoint_tester", defaults={"email": "endpoint_tester@example.com"})
if created or not user.has_usable_password():
    user.set_password("TempPass123!")
    user.save()
client.force_login(user)
print(f"Authenticated as: {user.username}")


def pick(dct, keys, default=None):
    if not isinstance(dct, dict):
        return default
    for k in keys:
        if dct.get(k) is not None:
            return dct.get(k)
    return default


def container(payload):
    if not isinstance(payload, dict):
        return {}
    for k in ("data", "result", "analysis", "structured_data", "resume_data"):
        if isinstance(payload.get(k), dict):
            return payload[k]
    return payload


def count_of(v):
    return len(v) if isinstance(v, (list, tuple, set, dict, str)) else 0


def call_endpoint(path):
    upload = SimpleUploadedFile("resume.pdf", file_bytes, content_type="application/pdf")
    response = client.post(path, {"file": upload})
    print(f"\n=== Endpoint: {path} ===")
    print(f"status code: {response.status_code}")
    try:
        payload = response.json()
    except Exception as e:
        print(f"non_json_error: {e}")
        print(f"body_preview: {response.content[:400]!r}")
        return response.status_code, {}

    if isinstance(payload, dict):
        print(f"key fields present: {sorted(payload.keys())}")
        if payload.get("error") is not None:
            print(f"json_error: {payload.get('error')}")
        if payload.get("errors") is not None:
            print(f"json_errors: {payload.get('errors')}")
    else:
        print(f"key fields present: <{type(payload).__name__}>")
    return response.status_code, payload

results = {}

# phase 1
s, p = call_endpoint("/resumes/phase1/extract-text/")
c = container(p)
text_preview = pick(c, ["text_preview", "preview"]) or pick(p, ["text_preview", "preview"]) or ""
if not text_preview:
    extracted = pick(c, ["extracted_text", "text"]) or pick(p, ["extracted_text", "text"]) or ""
    text_preview = extracted[:300] if isinstance(extracted, str) else ""
print(f"phase1: len(text_preview)={len(text_preview)}")
results["phase1"] = (200 <= s < 300) and len(text_preview) > 0 and not (isinstance(p, dict) and (p.get("error") or p.get("errors")))

# phase 2
s, p = call_endpoint("/resumes/phase2/extract-structured/")
c = container(p)
name_val = pick(c, ["name", "candidate_name", "full_name"]) or pick(p, ["name", "candidate_name", "full_name"])
skills = pick(c, ["skills"]) or pick(p, ["skills"]) or []
print(f"phase2: name exists={bool(name_val)}, skills count={count_of(skills)}")
results["phase2"] = (200 <= s < 300) and bool(name_val) and isinstance(skills, (list, tuple, set)) and not (isinstance(p, dict) and (p.get("error") or p.get("errors")))

# phase 3
s, p = call_endpoint("/resumes/phase3/safe-extract/")
c = container(p)
skills = pick(c, ["skills"]) or pick(p, ["skills"]) or []
featured = pick(c, ["featured_job"]) or pick(p, ["featured_job"])
recs = pick(c, ["recommendations"]) or pick(p, ["recommendations"]) or []
insights = pick(c, ["market_insights"]) or pick(p, ["market_insights"]) or []
print(f"phase3: skills count={count_of(skills)}, featured_job exists={bool(featured)}, recommendations count={count_of(recs)}, market_insights count={count_of(insights)}")
results["phase3"] = (200 <= s < 300) and bool(featured) and isinstance(recs, (list, tuple)) and isinstance(insights, (list, tuple)) and not (isinstance(p, dict) and (p.get("error") or p.get("errors")))

# analyze-resume
s, p = call_endpoint("/analyze-resume/")
c = container(p)
skills = pick(c, ["skills"]) or pick(p, ["skills"]) or []
featured = pick(c, ["featured_job"]) or pick(p, ["featured_job"])
recs = pick(c, ["recommendations"]) or pick(p, ["recommendations"]) or []
insights = pick(c, ["market_insights"]) or pick(p, ["market_insights"]) or []
print(f"analyze-resume: skills count={count_of(skills)}, featured_job exists={bool(featured)}, recommendations count={count_of(recs)}, market_insights count={count_of(insights)}")
results["analyze-resume"] = (200 <= s < 300) and bool(featured) and isinstance(recs, (list, tuple)) and isinstance(insights, (list, tuple)) and not (isinstance(p, dict) and (p.get("error") or p.get("errors")))

print("\n=== PASS/FAIL SUMMARY ===")
for k in ["phase1", "phase2", "phase3", "analyze-resume"]:
    print(f"{k}: {'PASS' if results[k] else 'FAIL'}")
print(f"overall: {'PASS' if all(results.values()) else 'FAIL'}")
