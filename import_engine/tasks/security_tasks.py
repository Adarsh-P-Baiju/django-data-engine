import os
import logging
from celery import shared_task
from django.conf import settings
from import_engine.domain.models import ImportJob
from import_engine.services.security_service import VirusScanner

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def security_scan_task(self, job_id):
    """
    Background task to scan staged files for viruses before moving to storage.
    """
    try:
        job = ImportJob.objects.get(id=job_id)
        
        if not job.local_path or not os.path.exists(job.local_path):
            job.status = ImportJob.Status.FAILED
            job.error_message = "Staged file not found for scanning."
            job.save(update_fields=["status", "error_message"])
            return

        # 1. Update Status to SCANNING
        job.status = ImportJob.Status.SCANNING
        job.status_message = "Initiating virus scan on staged file..."
        job.save(update_fields=["status", "status_message"])
        logger.info({"event": "scan_started", "job_id": str(job_id)})

        # 2. Run Scan
        with VirusScanner() as scanner:
            try:
                is_clean, virus_name = scanner.scan_file(job.local_path)
            except Exception as e:
                # Handle connection errors based on fail-safe setting
                if getattr(settings, "CLAMAV_FAIL_SAFE", True):
                    logger.critical(f"ClamAV Connection Failed for Job {job_id}. FAIL-SAFE ENABLED: Passing file.")
                    is_clean, virus_name = True, None
                else:
                    logger.error(f"ClamAV Connection Failed for Job {job_id}. FAIL-SAFE DISABLED: Failing job.")
                    raise RuntimeError(f"Could not connect to ClamAV: {e}")

        if not is_clean:
            job.status = ImportJob.Status.INFECTED
            job.status_message = f"Infected: {virus_name}"
            job.error_message = f"Security Alert: File infected with {virus_name}."
            job.save(update_fields=["status", "status_message", "error_message"])
            logger.warning({"event": "scan_infected", "job_id": str(job_id), "virus": virus_name})
            if os.path.exists(job.local_path):
                os.remove(job.local_path)
            return

        # 3. Transition to Storage (MinIO)
        job.status = ImportJob.Status.CLEAN
        job.status_message = "File clean. Transferring to permanent storage (MinIO)..."
        job.save(update_fields=["status", "status_message"])

        with open(job.local_path, "rb") as f:
            storage_name = f"{job.id}_{job.original_filename}"
            # Django's FileField.save handles streaming if we pass the file object
            job.file.save(storage_name, f, save=True)

        job.status_message = "Transfer complete. Initiating row orchestration..."
        job.save(update_fields=["status_message"])

        logger.info({"event": "scan_clean", "job_id": str(job_id)})

        # 4. Kick off Orchestration
        from import_engine.tasks.processing_tasks import generate_chunks_task
        generate_chunks_task.apply_async(args=[job.id], queue="heavy_tasks")

        # Cleanup local file after move
        if os.path.exists(job.local_path):
            os.remove(job.local_path)

    except ImportJob.DoesNotExist:
        logger.error(f"Job {job_id} not found during security scan.")
    except Exception as exc:
        logger.error({"event": "scan_error", "job_id": str(job_id), "error": str(exc)})
        raise self.retry(exc=exc, countdown=60)
