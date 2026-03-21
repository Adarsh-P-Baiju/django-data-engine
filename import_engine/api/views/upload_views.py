from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.http import HttpResponse

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse, OpenApiTypes

from import_engine.services.upload_service import handle_upload
from import_engine.api.throttling import UploadUserRateThrottle, UploadAnonRateThrottle
from import_engine.domain.config_registry import get_config
from import_engine.utils.template_generator import generate_template

class ImportUploadView(APIView):
    throttle_classes = [UploadUserRateThrottle, UploadAnonRateThrottle]

    @extend_schema(
        summary="Upload Data File",
        description="Uploads an Excel (.xlsx, .xls) or CSV file for asynchronous processing into the specified model.",
        parameters=[
            OpenApiParameter(name="model_name", description="The registered model name (e.g. 'user', 'organization')", type=str, location=OpenApiParameter.PATH),
        ],
        request={
            'multipart/form-data': {
                'type': 'object',
                'properties': {
                    'file': {
                        'type': 'string',
                        'format': 'binary'
                    }
                }
            }
        },
        responses={
            202: OpenApiResponse(description="File accepted for processing."),
            400: OpenApiResponse(description="Validation error or file missing."),
            404: OpenApiResponse(description="Model not registered in ConfigRegistry.")
        }
    )
    def post(self, request, model_name):
        file = request.FILES.get("file")
        if not file:
            return Response({"error": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
            
        config = get_config(model_name)
        if not config:
            return Response({"error": f"Model '{model_name}' not registered."}, status=status.HTTP_404_NOT_FOUND)
            
        try:
            job = handle_upload(model_name, file)
            return Response({
                "job_id": str(job.id),
                "status": job.status,
                "message": "File accepted and scanning completed."
            }, status=status.HTTP_202_ACCEPTED)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Internal error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class TemplateDownloadView(APIView):
    @extend_schema(
        summary="Download Excel Template",
        description="Generates and downloads an Excel template with embedded dropdowns and highlight constraints based on the target model's Validation DSL.",
        parameters=[
            OpenApiParameter(name="model_name", description="The registered model name", type=str, location=OpenApiParameter.PATH),
        ],
        responses={
            200: OpenApiResponse(description="The Excel file binary payload", response=OpenApiTypes.BINARY),
            404: OpenApiResponse(description="Model not registered.")
        }
    )
    def get(self, request, model_name):
        config = get_config(model_name)
        if not config:
            return Response({"error": f"Model '{model_name}' not registered."}, status=status.HTTP_404_NOT_FOUND)
            
        output = generate_template(config)
        response = HttpResponse(
            output, 
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename={model_name}_template.xlsx'
        return response
