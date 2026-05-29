from django import forms


class ResumeUploadForm(forms.Form):
    resume = forms.FileField(
        label="Upload your resume",
        help_text="PDF or DOCX, maximum 5MB",
    )

    def clean_resume(self):
        resume = self.cleaned_data["resume"]
        name = resume.name.lower()
        if not (name.endswith(".pdf") or name.endswith(".docx")):
            raise forms.ValidationError("Please upload a PDF or DOCX resume.")
        if resume.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Please upload a resume smaller than 5MB.")
        return resume
