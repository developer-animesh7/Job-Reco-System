from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from resume_analyzer.views import _resolve_request_user

from .forms import ResumeUploadForm
from .services import ResumeProcessingError, process_resume


def legacy_home(request):
    context = {"form": ResumeUploadForm()}

    if request.method == "POST":
        form = ResumeUploadForm(request.POST, request.FILES)
        context["form"] = form

        if form.is_valid():
            try:
                context.update(process_resume(form.cleaned_data["resume"], _resolve_request_user(request)))
            except ResumeProcessingError as exc:
                context["error"] = str(exc)
            except Exception:
                context["error"] = "Unable to process the resume right now."

    return render(request, "recommender/index.html", context)


@csrf_exempt
@require_http_methods(["POST"])
def api_analyze_resume(request):
    form = ResumeUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)

    try:
        result = process_resume(form.cleaned_data["resume"], _resolve_request_user(request))
    except ResumeProcessingError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception:
        return JsonResponse({"error": "Unable to process the resume right now."}, status=500)

    return JsonResponse({"result": result}, status=201)
