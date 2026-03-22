from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter

from import_engine.domain.models import ImportJob, ImportChunk, ImportLog
from import_engine.api.serializers import (
    ImportJobSerializer,
    ImportChunkSerializer,
    ImportLogSerializer,
)


class JobStatusView(APIView):
    @extend_schema(
        summary="Get Job Status",
        description="Poll this endpoint to retrieve the latest state, success/failure counts, and fingerprint data of an Import Job.",
        responses={200: ImportJobSerializer},
    )
    def get(self, request, job_id):
        job = get_object_or_404(ImportJob, id=job_id)
        serializer = ImportJobSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)


class JobChunksView(APIView):
    @extend_schema(
        summary="Get Job Chunks",
        description="Returns the execution status of all parallel Celery chunks associated with this Import Job.",
        responses={200: ImportChunkSerializer(many=True)},
    )
    def get(self, request, job_id):
        job = get_object_or_404(ImportJob, id=job_id)
        chunks = ImportChunk.objects.filter(job=job).order_by("chunk_index")
        serializer = ImportChunkSerializer(chunks, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class JobLogsView(APIView):
    @extend_schema(
        summary="Get Job Error Logs",
        description="Retrieves a paginated Dead-Letter Queue (DLQ) of all row-level failure logs for a given job.",
        parameters=[
            OpenApiParameter(
                name="page", description="Page number", required=False, type=int
            ),
            OpenApiParameter(
                name="page_size",
                description="Number of results per page",
                required=False,
                type=int,
            ),
        ],
    )
    def get(self, request, job_id):
        job = get_object_or_404(ImportJob, id=job_id)
        logs = ImportLog.objects.filter(job=job).order_by("row_number")

        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 50))

        start = (page - 1) * page_size
        end = start + page_size

        serializer = ImportLogSerializer(logs[start:end], many=True)
        return Response(
            {
                "total_errors": logs.count(),
                "page": page,
                "page_size": page_size,
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
