import os
import hashlib
import tempfile
import logging
import shutil

from django.db import transaction

from import_engine.domain.models import ImportJob
from import_engine.api.file_validators import (
    validate_file_size,
    validate_file_extension,
)

logger = logging.getLogger(__name__)

def compute_file_fingerprint(file_path: str) -> str:
    """Computes SHA-256 hash of a file for identity verification."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in 4KB chunks to be memory efficient
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def handle_upload(model_name: str, uploaded_file) -> ImportJob:
    """Async-ready upload handler with shared volume streaming."""
    # 1. Preliminary Validation (Size & Extension)
    validate_file_size(uploaded_file)
    validate_file_extension(uploaded_file)

    # 2. Zero-Memory Streaming to Shared Volume (/tmp/uploads)
    os.makedirs("/tmp/uploads", exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(
        dir="/tmp/uploads", prefix=f"import_{model_name}_"
    )

    try:
        with os.fdopen(temp_fd, "wb") as tmp:
            # Use shutil.copyfileobj for efficient streaming from Django's uploaded file
            shutil.copyfileobj(uploaded_file, tmp)

        # Make file world-readable so ClamAV container can read it
        os.chmod(temp_path, 0o644)

        # 3. Identity Verification (Fingerprinting)
        fingerprint = compute_file_fingerprint(temp_path)

        # Check for duplicate active jobs
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
            logger.info(
                f"De-duplication: Found existing job {duplicate.id} for the same file."
            )
            os.remove(temp_path)
            return duplicate

        # 4. Atomic Job Initial Creation (Staging)
        with transaction.atomic():
            job = ImportJob.objects.create(
                model_name=model_name,
                original_filename=uploaded_file.name,
                file_fingerprint=fingerprint,
                local_path=temp_path,
                status=ImportJob.Status.PENDING,
                status_message=f"File staged in temporary storage: {temp_path}"
            )

        # 5. Dispatch to Async Scanning
        from import_engine.tasks.security_tasks import security_scan_task
        security_scan_task.apply_async(args=[job.id], queue="heavy_tasks")

        logger.info(f"Upload Staged: Created Job {job.id} at {temp_path}. Background scan started.")
        return job

    except Exception as e:
        logger.error(f"Upload Staging Failed for {model_name}: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

def handle_streaming_upload(model_name: str, request) -> ImportJob:
    """Reads directly from the request stream for massive datasets."""
    os.makedirs("/tmp/uploads", exist_ok=True)
    temp_fd, temp_path = tempfile.mkstemp(
        dir="/tmp/uploads", prefix=f"stream_{model_name}_"
    )

    try:
        with os.fdopen(temp_fd, "wb") as tmp:
            django_request = getattr(request, "_request", request)

            # Streaming copy from request stream to file
            while True:
                chunk = django_request.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                tmp.write(chunk)

        # Make file world-readable so ClamAV container can read it
        os.chmod(temp_path, 0o644)

        fingerprint = compute_file_fingerprint(temp_path)

        with transaction.atomic():
            job = ImportJob.objects.create(
                model_name=model_name,
                original_filename="streamed_dataset.csv",  # fallback name
                file_fingerprint=fingerprint,
                local_path=temp_path,
                status=ImportJob.Status.PENDING,
                status_message=f"Streamed file staged: {temp_path}"
            )

        from import_engine.tasks.security_tasks import security_scan_task
        security_scan_task.apply_async(args=[job.id], queue="heavy_tasks")
        
        return job

    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
