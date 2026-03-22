import os
import uuid
from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.db import transaction

from import_engine.domain.models import ImportJob
from import_engine.services.security_service import VirusScanner
from import_engine.api.file_validators import (
    validate_file_size,
    validate_file_extension,
)


def handle_upload(model_name: str, uploaded_file) -> ImportJob:
    """
    Handles secure file upload with ClamAV scan-before-save enforcing the ephemeral volume.
    Persists to MinIO ONLY if the file is clean.
    """
    validate_file_size(uploaded_file)
    validate_file_extension(uploaded_file)

    scanner = VirusScanner()

    tmp_dir = "/tmp/uploads"
    os.makedirs(tmp_dir, exist_ok=True)

    temp_filename = f"{uuid.uuid4().hex}_{uploaded_file.name}"
    temp_path = os.path.join(tmp_dir, temp_filename)

    with open(temp_path, "wb+") as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)

    try:
        is_clean, virus_name = scanner.scan_file(temp_path)

        if not is_clean:
            raise ValidationError(
                f"Security Alert: File infected with {virus_name}. Upload rejected."
            )

        with transaction.atomic():
            job = ImportJob.objects.create(
                model_name=model_name,
                original_filename=uploaded_file.name,
                status=ImportJob.Status.PENDING,
            )

            with open(temp_path, "rb") as clean_file:
                random_name = f"{job.id}_{uploaded_file.name}"
                job.file.save(random_name, ContentFile(clean_file.read()), save=True)

        # Trigger Celery Dispatch
        from import_engine.execution_engine.orchestrator import dispatch_import_job

        dispatch_import_job(job.id)

        return job

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
