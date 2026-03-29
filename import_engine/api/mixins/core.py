import logging
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiTypes

from import_engine.services.upload_service import handle_upload, handle_streaming_upload
from import_engine.domain.config_registry import get_config
from import_engine.utils.template_generator import generate_template
from import_engine.api.throttling import UploadUserRateThrottle, UploadAnonRateThrottle

logger = logging.getLogger(__name__)

class ImportMixin:
    """
    Ultra-advanced DRF ViewSet Mixin for Model-centric Data Imports.
    Provides polymorphic endpoints for secure uploads and dynamic template generation.
    """
    
    # Default throttles for import actions
    import_throttle_classes = [UploadUserRateThrottle, UploadAnonRateThrottle]

    def get_import_model_name(self) -> str:
        """Resolves the model name for the import engine."""
        if hasattr(self, "import_model_name"):
            return self.import_model_name
        
        qs = getattr(self, "get_queryset", lambda: getattr(self, "queryset", None))()
        if qs is not None:
            return qs.model.__name__
            
        raise ValueError("ImportMixin requires 'import_model_name' or a 'queryset' on the ViewSet.")

    def get_throttles(self):
        """Dynamic throttling: Apply import throttles only to import actions."""
        if self.action in ["import_data", "download_template"]:
            return [t() for t in self.import_throttle_classes]
        return super().get_throttles()

    @extend_schema(
        summary="Analyze Data File",
        description="Analyzes a sample of the file to suggest model mappings and validation rules without starting an import job.",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
            }
        },
        responses={200: OpenApiResponse(description="Inferred configuration results.")},
    )
    @action(detail=False, methods=["post"], url_path="analyze")
    def analyze_data(self, request, *args, **kwargs):
        """Endpoint for zero-config schema inference."""
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        from import_engine.services.auto_config_service import AutoConfigService
        result = AutoConfigService.analyze_file(file, file.name)
        
        if "error" in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Upload Data File",
        description="Securely uploads a CSV/Excel file for the target Model. Scans for viruses and de-duplicates identical pending files.",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"file": {"type": "string", "format": "binary"}},
            }
        },
        responses={
            202: OpenApiResponse(description="File accepted for background processing."),
            400: OpenApiResponse(description="Validation error."),
            404: OpenApiResponse(description="Model not registered."),
            429: OpenApiResponse(description="Rate limit exceeded."),
        },
    )
    @action(detail=False, methods=["post"], url_path="import")
    def import_data(self, request, *args, **kwargs):
        model_name = self.get_import_model_name()
        if not get_config(model_name):
            return Response({"error": f"Model '{model_name}' not registered."}, status=status.HTTP_404_NOT_FOUND)

        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            job = handle_upload(model_name, file)
            return Response({
                "job_id": str(job.id),
                "status": job.status,
                "message": "File accepted for processing.",
            }, status=status.HTTP_202_ACCEPTED)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"Import Error for {model_name}: {e}")
            return Response({"error": "Internal Engine Error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        summary="Stream Large Data File",
        description="High-performance binary stream upload. Bypasses multipart parsing for 10GB+ file support. Pass data as raw binary in POST body.",
        request=OpenApiTypes.BINARY,
        responses={202: OpenApiResponse(description="Stream accepted.")},
    )
    @action(detail=False, methods=["post"], url_path="import/stream")
    def stream_data(self, request, *args, **kwargs):
        """Zero-copy stream ingestion for massive datasets."""
        model_name = self.get_import_model_name()
        if not get_config(model_name):
            return Response({"error": f"Model '{model_name}' not registered."}, status=status.HTTP_404_NOT_FOUND)

        try:
            job = handle_streaming_upload(model_name, request)
            return Response({
                "job_id": str(job.id),
                "status": job.status,
                "message": "Binary stream accepted for processing.",
            }, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            logger.exception(f"Streaming Error for {model_name}: {e}")
            return Response({"error": "Streaming Injection Failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        summary="Download Template",
        description="Downloads a dynamically generated Excel template with validation constraints.",
        responses={
            200: OpenApiResponse(description="Excel binary payload.", response=OpenApiTypes.BINARY),
            404: OpenApiResponse(description="Model not registered."),
        },
    )
    @action(detail=False, methods=["get"], url_path="import/template")
    def download_template(self, request, *args, **kwargs):
        model_name = self.get_import_model_name()
        config = get_config(model_name)
        if not config:
            return Response({"error": f"Model '{model_name}' not registered."}, status=status.HTTP_404_NOT_FOUND)

        try:
            output = generate_template(config)
            response = HttpResponse(output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={model_name}_template.xlsx"
            return response
        except Exception as e:
            logger.exception(f"Template Error for {model_name}: {e}")
            return Response({"error": "Template Generation Failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
