import os
import re
import uuid
import zipfile

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_MIME_TYPES = {PDF_MIME, DOCX_MIME}


CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def secure_resume_upload_path(instance, filename):
    """Store files with randomized names to avoid trusting user-supplied names."""
    extension = os.path.splitext(filename)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        extension = ".bin"
    return f"resumes/{uuid.uuid4().hex}{extension}"


def _safe_seek(uploaded_file, position):
    try:
        uploaded_file.seek(position)
    except Exception:
        pass


def detect_mime_by_signature(uploaded_file):
    """Determine MIME using file signature and DOCX archive structure."""
    _safe_seek(uploaded_file, 0)
    header = uploaded_file.read(8)
    _safe_seek(uploaded_file, 0)

    if header.startswith(b"%PDF-"):
        return PDF_MIME

    # DOCX files are ZIP archives containing Word-specific entries.
    if header.startswith(b"PK\x03\x04"):
        try:
            _safe_seek(uploaded_file, 0)
            with zipfile.ZipFile(uploaded_file) as zip_file:
                found_content_types = False
                found_word_entry = False
                for zip_info in zip_file.infolist():
                    name = zip_info.filename
                    if name == "[Content_Types].xml":
                        found_content_types = True
                    elif name.startswith("word/"):
                        found_word_entry = True

                    if found_content_types and found_word_entry:
                        return DOCX_MIME
        except (zipfile.BadZipFile, OSError):
            return "unknown"
        finally:
            _safe_seek(uploaded_file, 0)

    return "unknown"


def sanitize_text(value):
    if value is None:
        return ""
    cleaned = CONTROL_CHARS_RE.sub("", str(value))
    return cleaned.strip()


def sanitize_skills(skills):
    if not isinstance(skills, list):
        return []

    cleaned = []
    seen = set()
    for skill in skills:
        skill_text = sanitize_text(skill)
        if not skill_text:
            continue
        key = skill_text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(skill_text[:100])

    return cleaned


def validate_resume_upload(uploaded_file):
    if uploaded_file is None:
        return "Empty upload. Please select a file."

    if uploaded_file.size <= 0:
        return "Empty upload. Please select a file."

    if uploaded_file.size > MAX_FILE_SIZE_BYTES:
        return "File too large. Maximum size is 5MB."

    extension = os.path.splitext(uploaded_file.name)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        return "Invalid file type. Only PDF and DOCX are allowed."

    claimed_mime = sanitize_text(getattr(uploaded_file, "content_type", ""))
    if claimed_mime not in ALLOWED_MIME_TYPES:
        return "Invalid MIME type for resume upload."

    detected_mime = detect_mime_by_signature(uploaded_file)
    if detected_mime == "unknown":
        return "File content does not match allowed PDF/DOCX signatures."

    expected_mime = PDF_MIME if extension == ".pdf" else DOCX_MIME
    if detected_mime != expected_mime:
        return "File extension and file signature do not match."

    return None
