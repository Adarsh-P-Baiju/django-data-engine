import logging
from typing import Tuple
from django.db import transaction
from import_engine.domain.models import ImportJob

logger = logging.getLogger(__name__)

class RollbackService:
    """
    Enterprise Rollback Service.
    Provides atomic, job-level recovery by purging imported records.
    """
    
    @staticmethod
    def rollback_job(job_id: str) -> Tuple[bool, str]:
        """
        Atomically rolls back an entire import job.
        Deletes all records created by this job across all target models.
        """
        try:
            job = ImportJob.objects.get(id=job_id)
            
            if job.status not in [ImportJob.Status.COMPLETED, ImportJob.Status.FAILED]:
                msg = f"Rollback: Job {job_id} is in status {job.status}. Rollback allowed only for final states."
                logger.warning(msg)
                return False, msg

            with transaction.atomic():
                # 1. Resolve the model class from the job's model_name
                from import_engine.domain.config_registry import get_config
                config = get_config(job.model_name)
                if not config:
                    return False, f"Config not found for model {job.model_name}"
                
                model_class = config.model
                
                # 2. Check if the model has a job_id tracking field
                if not hasattr(model_class, "import_job"):
                    msg = f"Model {model_class.__name__} does not support rollback (missing import_job field)."
                    logger.error(f"Rollback: {msg}")
                    return False, msg

                # 3. Delete all records created by this job
                deleted_count, _ = model_class.objects.filter(import_job=job).delete()
                
                # 4. Clean up logs and chunks
                job.logs.all().delete()
                job.chunks.all().delete()
                
                # 5. Reset job stats
                job.status = ImportJob.Status.PENDING 
                job.success_count = 0
                job.failure_count = 0
                job.processed_rows = 0
                job.error_message = f"Job rolled back. Deleted {deleted_count} records."
                job.save()

                success_msg = f"Successfully rolled back Job {job_id}. Deleted {deleted_count} records."
                logger.info(f"Rollback: {success_msg}")
                return True, success_msg

        except ImportJob.DoesNotExist:
            return False, f"Job {job_id} does not exist."
        except Exception as e:
            logger.exception(f"Rollback: Failed for Job {job_id}: {e}")
            return False, str(e)
