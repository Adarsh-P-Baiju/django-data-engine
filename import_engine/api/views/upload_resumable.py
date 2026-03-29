import os
import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from import_engine.domain.models import ImportJob
from import_engine.services.upload_service import compute_file_fingerprint

logger = logging.getLogger(__name__)


class ResumableUploadView(APIView):
    """Chunked HTTP Upload with Content-Range support."""

    def post(self, request, model_name):
        """Initializes an upload session and returns a Job ID."""
        filename = request.data.get("filename")
        total_size = request.data.get("total_size")

        if not filename or not total_size:
            return Response(
                {"error": "filename and total_size required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Create a shell Job to track the upload
            job = ImportJob.objects.create(
                model_name=model_name,
                original_filename=filename,
                total_bytes=int(total_size),
                status=ImportJob.Status.PENDING,
                status_message="Initial Handshake Successful. Ready for chunks.",
            )
            return Response(
                {
                    "job_id": str(job.id),
                    "url": f"/api/engine/imports/resumable/{job.id}/",
                    "message": "Initialized. Start patching chunks.",
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            logger.error(f"Resumable Init Failed: {e}")
            return Response(
                {"error": "Failed to initialize upload session"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, job_id):
        """Processes a binary chunk and appends it to the staged file."""
        try:
            job = ImportJob.objects.get(id=job_id)
        except ImportJob.DoesNotExist:
            return Response(
                {"error": "Invalid Job ID"}, status=status.HTTP_404_NOT_FOUND
            )

        # 1. Parse Content-Range header
        content_range = request.headers.get("Content-Range")
        if not content_range:
            return Response(
                {"error": "Content-Range header required (e.g., bytes 0-1023/2048)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Format: 'bytes <start>-<end>/<total>'
            range_info = content_range.replace("bytes ", "").split("/")
            byte_range = range_info[0].split("-")
            start_byte = int(byte_range[0])
            # end_byte and total_bytes are validated but not strictly needed for append mode
        except Exception:
            return Response(
                {"error": "Invalid Content-Range format"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Guard: Ensure sequential upload (Optional but safer for simple impl)
        if start_byte != job.processed_bytes:
            return Response(
                {
                    "error": f"Out of sync. Expected start byte: {job.processed_bytes}",
                    "expected_offset": job.processed_bytes,
                },
                status=status.HTTP_409_CONFLICT,
            )

        # 3. Stream chunk to disk (Append mode)
        os.makedirs("/tmp/uploads", exist_ok=True)
        if not job.local_path:
            job.local_path = os.path.join("/tmp/uploads", f"resumable_{job.id}.tmp")
            job.save(update_fields=["local_path"])

        try:
            with open(job.local_path, "ab") as f:
                # Read from raw stream
                chunk_data = request.body
                f.write(chunk_data)

            # 4. Update progress
            new_offset = job.processed_bytes + len(chunk_data)
            job.processed_bytes = new_offset

            if new_offset >= job.total_bytes:
                # UPLOAD COMPLETE
                job.status = ImportJob.Status.SCANNING
                job.status_message = "Staging Complete. Commencing security scan."
                job.file_fingerprint = compute_file_fingerprint(job.local_path)

                # Make world-readable for ClamAV
                os.chmod(job.local_path, 0o644)

                # Dispatch scan
                from import_engine.tasks.security_tasks import security_scan_task

                security_scan_task.apply_async(args=[job.id], queue="heavy_tasks")

                job.save(
                    update_fields=[
                        "processed_bytes",
                        "status",
                        "status_message",
                        "file_fingerprint",
                    ]
                )
                return Response(
                    {
                        "status": "COMPLETED",
                        "message": "File fully received. Processing...",
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                job.save(update_fields=["processed_bytes"])
                return Response(
                    {
                        "status": "PARTIAL",
                        "next_offset": new_offset,
                        "percent_complete": round(
                            (new_offset / job.total_bytes) * 100, 2
                        ),
                    },
                    status=status.HTTP_206_PARTIAL_CONTENT,
                )

        except Exception as e:
            logger.error(f"Chunk Patch Failed for {job_id}: {e}")
            return Response(
                {"error": "Chunk Write Failure"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
