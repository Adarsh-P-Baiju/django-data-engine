import logging

from rest_framework import viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from import_engine.domain.models import ImportJob, ImportChunk, ImportLog
from import_engine.api.serializers.core import (
    ImportJobSerializer,
    ImportChunkSerializer,
    ImportLogSerializer,
)
from import_engine.services.rollback_service import rollback_job

logger = logging.getLogger(__name__)

class ImportJobViewSet(mixins.RetrieveModelMixin, 
                       mixins.ListModelMixin, 
                       viewsets.GenericViewSet):
    """
    Polymorphic ViewSet for managing and monitoring Import Jobs.
    Provides real-time status tracking, chunk execution details, 
    paginated error logs, and atomic rollback capabilities.
    """
    queryset = ImportJob.objects.all().order_by("-created_at")
    serializer_class = ImportJobSerializer

    @extend_schema(
        summary="Rollback Import Job",
        description="Atomically deletes all records created by this job. Only supported for models using ImportedModelMixin.",
        responses={
            200: {"type": "object", "properties": {"message": {"type": "string"}}},
            400: {"type": "object", "properties": {"error": {"type": "string"}}},
        },
    )
    @action(detail=True, methods=["post"])
    def rollback(self, request, pk=None):
        """Triggers the rollback service for this specific job."""
        if rollback_job(pk):
            return Response({"message": "Job rolled back successfully."}, status=status.HTTP_200_OK)
        return Response({"error": "Rollback failed. Verify the model supports rollback and the job is in a valid state."}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Get Job Chunks",
        description="Returns the execution status of all parallel Celery chunks associated with this Import Job.",
        responses={200: ImportChunkSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def chunks(self, request, pk=None):
        job = self.get_object()
        chunks = ImportChunk.objects.filter(job=job).order_by("chunk_index")
        serializer = ImportChunkSerializer(chunks, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Get Job Error Logs",
        description="Retrieves a paginated list of row-level failure logs (DLQ).",
        parameters=[
            OpenApiParameter(name="page", description="Page number", required=False, type=int),
            OpenApiParameter(name="page_size", description="Number of results per page", required=False, type=int),
        ],
        responses={200: ImportLogSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        job = self.get_object()
        logs = ImportLog.objects.filter(job=job).order_by("row_number")

        # Use built-in pagination if possible, or manual slice for simplicity here
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))
        start = (page - 1) * page_size
        end = start + page_size

        serializer = ImportLogSerializer(logs[start:end], many=True)
        return Response({
            "total_errors": logs.count(),
            "page": page,
            "page_size": page_size,
            "results": serializer.data,
        })
