import logging
from celery import shared_task
from import_engine.domain.models import ImportJob

logger = logging.getLogger('import_engine.metrics')

@shared_task
def cleanup_job(job_id):
    """
    Runs on the light queue. Garbage collects the file from MinIO after successful import.
    """
    job = ImportJob.objects.get(id=job_id)
    if job.file:
        job.file.delete(save=False)
        
    logger.info({
        "event": "job_cleanup_completed",
        "job_id": str(job.id)
    })
