import os
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from import_engine.domain.models import ImportJob

logger = logging.getLogger(__name__)


@shared_task
def cleanup_job(job_id):
    """Post-import cleanup for temporary artifacts."""
    try:
        job = ImportJob.objects.get(id=job_id)
        if job.local_path and os.path.exists(job.local_path):
            os.remove(job.local_path)
            logger.info(f"Cleanup: Removed local file for job {job_id}")
    except Exception as e:
        logger.error(f"Cleanup Failed for Job {job_id}: {e}")


@shared_task
def recover_stale_uploads():
    """
    Scans /tmp/uploads for files that are in PENDING status but not being processed.
    Self-healing mechanism for worker crashes.
    """
    logger.info("Starting recovery scan for stale uploads...")

    upload_dir = "/tmp/uploads"
    if not os.path.exists(upload_dir):
        return

    for filename in os.listdir(upload_dir):
        file_path = os.path.join(upload_dir, filename)


        if (
            timezone.now()
            - timezone.datetime.fromtimestamp(
                os.path.getmtime(file_path), tz=timezone.utc
            )
        ) < timedelta(minutes=5):
            continue


        job = ImportJob.objects.filter(
            local_path=file_path, status=ImportJob.Status.PENDING
        ).first()

        if job:
            from import_engine.tasks.security_tasks import security_scan_task

            logger.info(
                {
                    "event": "recovery_dispatch",
                    "job_id": str(job.id),
                    "file": file_path,
                    "status": job.status,
                }
            )
            security_scan_task.apply_async(args=[job.id], queue="heavy_tasks")
        else:


            if not ImportJob.objects.filter(local_path=file_path).exists():
                logger.info({"event": "recovery_cleanup_orphan", "file": file_path})
                os.remove(file_path)
