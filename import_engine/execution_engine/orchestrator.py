import logging


logger = logging.getLogger(__name__)

def dispatch_import_job(job_id: str):
    """
    Triggers the Celery pipeline to process the file in chunks.
    Dispatches the chunk generation as a background task.
    """
    from import_engine.tasks.processing_tasks import generate_chunks_task
    
    logger.info(f"Orchestrator: Dispatching chunk generation for Job {job_id}")
    generate_chunks_task.delay(job_id)
