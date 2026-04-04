from django.views.generic import View, TemplateView
from django.http import HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse

from import_engine.domain.config_registry import get_config
from import_engine.services.upload_service import handle_upload
from import_engine.utils.template_generator import generate_template
from import_engine.domain.models import ImportJob

import logging

logger = logging.getLogger(__name__)


class ImportUploadView(View):
    """Standard Django view for file upload."""

    def post(self, request, model_name, *args, **kwargs):
        if not get_config(model_name):
            return JsonResponse(
                {"error": f"Model '{model_name}' not registered."}, status=404
            )

        file = request.FILES.get("file")
        if not file:
            return JsonResponse({"error": "No file provided."}, status=400)

        try:
            job = handle_upload(model_name, file)

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "job_id": str(job.id),
                        "status": job.status,
                        "message": "File accepted for processing.",
                    },
                    status=202,
                )

            return HttpResponseRedirect(
                reverse("import_job_status", kwargs={"job_id": job.id})
            )
        except Exception as e:
            logger.exception(f"Upload error: {e}")
            return JsonResponse({"error": str(e)}, status=400)


class TemplateDownloadView(View):
    """Standard Django view for downloading templates."""

    def get(self, request, model_name, *args, **kwargs):
        config = get_config(model_name)
        if not config:
            return JsonResponse(
                {"error": f"Model '{model_name}' not registered."}, status=404
            )

        try:
            output = generate_template(config)
            response = HttpResponse(
                output,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = (
                f"attachment; filename={model_name}_template.xlsx"
            )
            return response
        except Exception as e:
            logger.exception(f"Template Error: {e}")
            return JsonResponse({"error": "Template Generation Failed"}, status=500)


class ImportJobStatusView(TemplateView):
    """View to track import job progress."""

    template_name = "import_engine/job_status.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job_id = self.kwargs.get("job_id")
        context["job"] = get_object_or_404(ImportJob, id=job_id)
        return context
