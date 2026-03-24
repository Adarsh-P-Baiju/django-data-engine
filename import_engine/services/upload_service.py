import os
import hashlib
import tempfile
import logging

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.db import transaction

from import_engine.domain.models import ImportJob
from import_engine.services.security_service import VirusScanner
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
    """
    Ultra-advanced secure upload handler with viral scanning, 
    SHA-256 fingerprinting, and automated de-duplication.
    """
    # 1. Preliminary Validation
    validate_file_size(uploaded_file)
    validate_file_extension(uploaded_file)

    # 2. Secure Temporary Persistence for Scanning
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        for chunk in uploaded_file.chunks():
            tmp.write(chunk)
        temp_path = tmp.name

    try:
        # 3. Security Scan (ClamAV)
        with VirusScanner() as scanner:
            is_clean, virus_name = scanner.scan_file(temp_path)
            if not is_clean:
                logger.warning(f"Security Alert: Infected file blocked! Virus: {virus_name}")
                raise ValidationError(f"Security Alert: File infected with {virus_name}.")

        # 4. Identity Verification (Fingerprinting)
        fingerprint = compute_file_fingerprint(temp_path)
        
        # Check for duplicate active jobs (Pending or Processing)
        duplicate = ImportJob.objects.filter(
            file_fingerprint=fingerprint,
            status__in=[ImportJob.Status.PENDING, ImportJob.Status.PROCESSING]
        ).first()
        
        if duplicate:
            logger.info(f"De-duplication: Found existing active job {duplicate.id} for the same file.")
            return duplicate

        # 5. Atomic Job Creation and Storage Transition
        with transaction.atomic():
            job = ImportJob.objects.create(
                model_name=model_name,
                original_filename=uploaded_file.name,
                file_fingerprint=fingerprint,
                status=ImportJob.Status.PENDING,
            )

            with open(temp_path, "rb") as clean_file:
                # Use a unique name in storage to avoid collisions
                random_name = f"{job.id}_{uploaded_file.name}"
                job.file.save(random_name, ContentFile(clean_file.read()), save=True)

        # 6. Kick off Orchestration
        from import_engine.execution_engine.orchestrator import dispatch_import_job
        dispatch_import_job(job.id)
        
        logger.info(f"Upload Success: Created Job {job.id} for model {model_name}")
        return job

    finally:
        # Guarantee cleanup of local temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
