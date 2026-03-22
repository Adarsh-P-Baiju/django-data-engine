from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.http import HttpResponse

from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiTypes

from import_engine.services.upload_service import handle_upload
from import_engine.domain.config_registry import get_config
from import_engine.utils.template_generator import generate_template


class ImportMixin:
    """
    A DRF ViewSet Mixin that provides built-in endpoints for Data Import via Excel/CSV.
    Requires `import_model_name` to be defined on the ViewSet,
    or falls back to the QuerySet model name.
    """

    def get_import_model_name(self):
        if hasattr(self, "import_model_name"):
            return self.import_model_name

        qs = getattr(self, "queryset", None)
        if qs is not None:
            return qs.model.__name__

        raise ValueError(
            "ImportMixin requires either `import_model_name` or `queryset` on the ViewSet."
        )

    @extend_schema(
        summary="Upload Data File for Model",
        description="Automatically securely uploads a CSV/Excel file for the parent ViewSet's target Model.",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
            }
        },
        responses={
            202: OpenApiResponse(
                description="File accepted for background processing."
            ),
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Model not registered."),
        },
    )
    @action(detail=False, methods=["post"], url_path="import")
    def import_data(self, request, *args, **kwargs):
        """
        Endpoint to securely upload and process a CSV/Excel file for this model.
        """
        model_name = self.get_import_model_name()

        if not get_config(model_name):
            return Response(
                {
                    "error": f"Model '{model_name}' is not registered with the Import Engine."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        file = request.FILES.get("file")
        if not file:
            return Response(
                {"error": "No file provided in the payload under the 'file' key."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            job = handle_upload(model_name, file)
            return Response(
                {
                    "job_id": str(job.id),
                    "status": job.status,
                    "message": "File accepted for background processing. ClamAV scan passed.",
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Internal Import Engine error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Download Template for Model",
        description="Downloads the Excel DSL template configured for the parent ViewSet's underlying Model.",
        responses={
            200: OpenApiResponse(
                description="Excel file.", response=OpenApiTypes.BINARY
            ),
            404: OpenApiResponse(description="Model not registered."),
        },
    )
    @action(detail=False, methods=["get"], url_path="import/template")
    def download_template(self, request, *args, **kwargs):
        """
        Endpoint to download a generated Excel template (with validation dropdowns) for this model.
        """
        model_name = self.get_import_model_name()
        config = get_config(model_name)

        if not config:
            return Response(
                {
                    "error": f"Model '{model_name}' is not registered with the Import Engine."
                },
                status=status.HTTP_404_NOT_FOUND,
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
            return Response(
                {"error": f"Internal Template Generation error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
