from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from import_engine.domain.models import ImportJob, ImportLog
from import_engine.api.serializers.core import (
    ImportJobSerializer,
    ImportChunkSerializer,
    ImportLogSerializer,
)
from import_engine.services.rollback_service import RollbackService


class ImportJobViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for job management, chunk monitoring, and rollbacks."""

    queryset = ImportJob.objects.all().order_by("-created_at")
    serializer_class = ImportJobSerializer

    @action(detail=True, methods=["get"])
    def chunks(self, request, pk=None):
        job = self.get_object()
        chunks = job.chunks.all().order_by("chunk_index")
        serializer = ImportChunkSerializer(chunks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def logs(self, request, pk=None):
        job = self.get_object()
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))

        logs = ImportLog.objects.filter(job=job).order_by("row_number")
        total = logs.count()

        start = (page - 1) * page_size
        end = start + page_size

        serializer = ImportLogSerializer(logs[start:end], many=True)
        return Response(
            {
                "total": total,
                "page": page,
                "page_size": page_size,
                "results": serializer.data,
            }
        )

    @action(detail=True, methods=["post"])
    def rollback(self, request, pk=None):
        """Perform atomic rollback of an import job."""
        job = self.get_object()
        if job.status not in [ImportJob.Status.COMPLETED, ImportJob.Status.FAILED]:
            return Response(
                {"error": "Only completed or failed jobs can be rolled back."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        success, message = RollbackService.rollback_job(job.id)
        if success:
            return Response({"message": message})
        return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)
