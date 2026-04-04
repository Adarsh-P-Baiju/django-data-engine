import os
import hashlib
import tempfile
import logging

from django.db import transaction
from django.core.files.base import ContentFile

from import_engine.domain.models import ImportJob
from import_engine.api.file_validators import (
    validate_file_size,
    validate_file_extension,
)
from import_engine.conf import import_engine_settings

logger = logging.getLogger(__name__)


def compute_file_fingerprint(file_path: str) -> str:
    """Computes SHA-256 hash of a file for identity verification."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def handle_upload(model_name: str, uploaded_file) -> ImportJob:
    """Storage-agnostic upload handler."""
    validate_file_size(uploaded_file)
    validate_file_extension(uploaded_file)


    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        temp_path = tmp_file.name
        try:
            for chunk in uploaded_file.chunks():
                tmp_file.write(chunk)
            tmp_file.flush()

            fingerprint = compute_file_fingerprint(temp_path)

            duplicate = ImportJob.objects.filter(
                file_fingerprint=fingerprint,
                status__in=[
                    ImportJob.Status.PENDING,
                    ImportJob.Status.SCANNING,
                    ImportJob.Status.CLEAN,
                    ImportJob.Status.PROCESSING,
                ],
            ).first()

            if duplicate:
                logger.info(f"De-duplication: Found existing job {duplicate.id}")
                return duplicate

            with transaction.atomic():
                job = ImportJob.objects.create(
                    model_name=model_name,
                    original_filename=uploaded_file.name,
                    file_fingerprint=fingerprint,
                    status=ImportJob.Status.PENDING,
                    status_message="File staged. Awaiting security scan.",
                )


                with open(temp_path, "rb") as f:
                    job.file.save(
                        f"pending/{job.id}_{uploaded_file.name}",
                        ContentFile(f.read()),
                        save=True,
                    )

            from import_engine.tasks.security_tasks import security_scan_task

            security_scan_task.apply_async(
                args=[job.id], queue=import_engine_settings.REGION_QUEUES.get("DEFAULT")
            )

            return job

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


def handle_streaming_upload(model_name: str, request) -> ImportJob:
    """Reads directly from request stream to storage."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        temp_path = tmp_file.name
        try:
            django_request = getattr(request, "_request", request)
            while True:
                chunk = django_request.read(1024 * 1024)
                if not chunk:
                    break
                tmp_file.write(chunk)
            tmp_file.flush()

            fingerprint = compute_file_fingerprint(temp_path)

            with transaction.atomic():
                job = ImportJob.objects.create(
                    model_name=model_name,
                    original_filename="streamed_dataset.csv",
                    file_fingerprint=fingerprint,
                    status=ImportJob.Status.PENDING,
                )

                with open(temp_path, "rb") as f:
                    job.file.save(
                        f"pending/{job.id}_streamed.csv",
                        ContentFile(f.read()),
                        save=True,
                    )

            from import_engine.tasks.security_tasks import security_scan_task

            security_scan_task.apply_async(
                args=[job.id], queue=import_engine_settings.REGION_QUEUES.get("DEFAULT")
            )

            return job

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
