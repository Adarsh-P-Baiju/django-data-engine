import os
import logging
import tempfile
from celery import shared_task
from import_engine.domain.models import ImportJob
from import_engine.services.security_service import VirusScanner
from import_engine.conf import import_engine_settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def security_scan_task(self, job_id):
    """
    Background task to scan staged files for viruses before moving to storage.
    Now downloads from project's storage to a local temp file for scanning.
    """
    try:
        job = ImportJob.objects.get(id=job_id)

        if not job.file:
            job.status = ImportJob.Status.FAILED
            job.error_message = "Staged file not found in storage."
            job.save(update_fields=["status", "error_message"])
            return


        job.status = ImportJob.Status.SCANNING
        job.status_message = "Downloading from storage for virus scan..."
        job.save(update_fields=["status", "status_message"])
        logger.info({"event": "scan_started", "job_id": str(job_id)})


        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            temp_path = tmp_file.name
            try:

                with job.file.open('rb') as stored_file:
                    for chunk in stored_file.chunks():
                        tmp_file.write(chunk)
                tmp_file.flush()


                with VirusScanner() as scanner:
                    try:
                        is_clean, virus_name = scanner.scan_file(temp_path)
                    except Exception as e:
                        if import_engine_settings.CLAMAV_FAIL_SAFE:
                            logger.critical(f"ClamAV Connection Failed for Job {job_id}. FAIL-SAFE ENABLED.")
                            is_clean, virus_name = True, None
                        else:
                            logger.error(f"ClamAV Connection Failed for Job {job_id}. FAIL-SAFE DISABLED.")
                            raise RuntimeError(f"Could not connect to ClamAV: {e}")

                if not is_clean:
                    job.status = ImportJob.Status.INFECTED
                    job.status_message = f"Infected: {virus_name}"
                    job.error_message = f"Security Alert: File infected with {virus_name}."
                    job.save(update_fields=["status", "status_message", "error_message"])


                    job.file.delete(save=False)
                    return


                job.status = ImportJob.Status.CLEAN
                job.status_message = "File clean. Ready for orchestration."
                job.save(update_fields=["status", "status_message"])

                logger.info({"event": "scan_clean", "job_id": str(job_id)})


                from import_engine.tasks.processing_tasks import generate_chunks_task
                generate_chunks_task.apply_async(
                    args=[job.id],
                    queue=import_engine_settings.REGION_QUEUES.get("DEFAULT")
                )

            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    except ImportJob.DoesNotExist:
        logger.error(f"Job {job_id} not found during security scan.")
    except Exception as exc:
        logger.error({"event": "scan_error", "job_id": str(job_id), "error": str(exc)})
        raise self.retry(exc=exc, countdown=60)
