import logging
from django.db import transaction
from import_engine.domain.models import ImportJob

logger = logging.getLogger(__name__)

def rollback_job(job_id: str) -> bool:
    """
    Atomically rolls back an entire import job.
    Deletes all records created by this job across all target models.
    """
    try:
        job = ImportJob.objects.get(id=job_id)
        
        if job.status != ImportJob.Status.COMPLETED and job.status != ImportJob.Status.FAILED:
            logger.warning(f"Rollback: Job {job_id} is in status {job.status}. Continuous rollbacks are not allowed.")
            return False

        with transaction.atomic():
            # 1. Resolve the model class from the job's model_name
            from import_engine.domain.config_registry import get_config
            config = get_config(job.model_name)
            if not config:
                raise ValueError(f"Config not found for model {job.model_name}")
            
            model_class = config.model
            
            # 2. Check if the model has a job_id tracking field
            if not hasattr(model_class, "import_job"):
                logger.error(f"Rollback: Model {model_class.__name__} does not support rollback (missing import_job field).")
                return False

            # 3. Delete all records created by this job
            deleted_count, _ = model_class.objects.filter(import_job=job).delete()
            
            # 4. Clean up logs and chunks
            job.logs.all().delete()
            job.chunks.all().delete()
            
            # 5. Reset job stats or delete the job record
            job.status = ImportJob.Status.PENDING # Or a new status like 'ROLLED_BACK'
            job.success_count = 0
            job.failure_count = 0
            job.processed_rows = 0
            job.error_message = f"Job rolled back. Deleted {deleted_count} records."
            job.save()

            logger.info(f"Rollback: Success for Job {job_id}. Deleted {deleted_count} records.")
            return True

    except ImportJob.DoesNotExist:
        logger.error(f"Rollback: Job {job_id} does not exist.")
        return False
    except Exception as e:
        logger.exception(f"Rollback: Failed for Job {job_id}: {e}")
        return False
