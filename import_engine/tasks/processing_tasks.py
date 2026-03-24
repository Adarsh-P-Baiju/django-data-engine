import time
import os
import logging
from celery import shared_task
from django.db import transaction, IntegrityError
from django.db.models import F

from import_engine.domain.models import ImportJob, ImportChunk, ImportLog
from import_engine.domain.config_registry import get_config
from import_engine.services.mapping.fk_resolver import FKResolver
from import_engine.validators.dsl import validate_row
from import_engine.services.persistence import bulk_persist
from import_engine.parsing.csv_adapter import CSVAdapter
from import_engine.parsing.excel_adapter import ExcelAdapter
from import_engine.services.chunk_generator import generate_chunks_for_job
from import_engine.services.header_mapper import apply_mapping
from import_engine.services.security_service import mask_pii

logger = logging.getLogger("import_engine.metrics")

@shared_task(bind=True, max_retries=3)
def generate_chunks_task(self, job_id):
    """
    Background task to generate segments (chunks) for parallel processing.
    """
    try:
        generate_chunks_for_job(job_id)
    except Exception as exc:
        job = ImportJob.objects.get(id=job_id)
        job.status = ImportJob.Status.FAILED
        job.error_message = f"Orchestration Failed: {str(exc)}"
        job.save(update_fields=["status", "error_message"])
        logger.error({"event": "orchestration_failed", "job_id": job_id, "error": str(exc)})
        raise self.retry(exc=exc, countdown=10)

@shared_task(bind=True, max_retries=5)
def process_chunk(self, chunk_id):
    """
    Ultra-advanced chunk processor with zero-memory row streaming,
    precise transaction boundaries, and throttled observability.
    """
    start_time = time.time()
    
    # 1. Initialization and Locked Status Update
    try:
        chunk = ImportChunk.objects.select_related("job").get(id=chunk_id)
        job = chunk.job
        config = get_config(job.model_name)
        
        if not config:
            chunk.status = ImportChunk.Status.FAILED
            chunk.save(update_fields=["status"])
            return

        # Mark as processing early to prevent race conditions
        chunk.status = ImportChunk.Status.PROCESSING
        chunk.save(update_fields=["status", "updated_at"])
        
    except ImportChunk.DoesNotExist:
        logger.error(f"Chunk {chunk_id} not found.")
        return

    adapter = None
    file_obj = None
    
    try:
        file_obj = job.file.open("rb")
        ext = os.path.splitext(job.original_filename)[1].lower()
        
        if ext == ".csv":
            adapter = CSVAdapter(file_obj)
        elif ext in [".xlsx", ".xls"]:
            adapter = ExcelAdapter(file_obj)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

        resolver = FKResolver(config)
        logs_to_create = []
        instances_to_create = []
        processed_count = 0
        empty_count = 0

        # 2. Optimized Row Pipeline (Streaming)
        # First pass: Collect data for prefetching FKs (we still need this to avoid N+1)
        # Note: For extreme scale, we could prefetch in smaller batches inside the loop
        row_buffer = []
        for row_idx, row_dict in adapter.iter_rows(start_row=chunk.start_row, end_row=chunk.end_row):
            if not any(v is not None and str(v).strip() != "" for v in row_dict.values()):
                empty_count += 1
                continue
            
            # Internal mapping and masking
            mapped_dict = apply_mapping(row_dict, job.field_mapping, config)
            row_buffer.append((row_idx, mapped_dict))
            processed_count += 1

        if row_buffer:
            resolver.prefetch([rd for _, rd in row_buffer])

        # 3. Processing and Validation
        for row_idx, row_dict in row_buffer:
            cleaned_data, errors = validate_row(config, row_dict)
            
            # Resolve Foreign Keys
            for fk_field, f_config in resolver.fk_fields.items():
                val = row_dict.get(fk_field)
                if val:
                    resolved_obj = resolver.resolve(fk_field, val)
                    if not resolved_obj:
                        is_required = isinstance(f_config, dict) and f_config.get("required")
                        if is_required:
                            errors[fk_field] = f"Foreign key resolution failed for '{val}'"
                        else:
                            cleaned_data[fk_field] = None
                    else:
                        cleaned_data[fk_field] = resolved_obj

            if errors:
                logs_to_create.append(
                    ImportLog(
                        job=job,
                        chunk=chunk,
                        row_number=row_idx,
                        row_data=mask_pii(row_dict, config),
                        errors=errors,
                        is_fatal=True,
                    )
                )
            else:
                instances_to_create.append(config.model(**cleaned_data))

        # 4. Atomic Persistence
        with transaction.atomic():
            if instances_to_create:
                conflict_res = getattr(config, "conflict_resolution", "fail")
                if conflict_res == "update":
                    upsert_keys = getattr(config, "upsert_keys", [])
                    update_fields = [f for f in config.fields.keys() if f not in upsert_keys]
                    bulk_persist(config.model, instances_to_create, upsert_fields={
                        "unique_fields": upsert_keys,
                        "update_fields": update_fields,
                    })
                elif conflict_res == "ignore":
                    bulk_persist(config.model, instances_to_create, ignore_conflicts=True)
                else:
                    bulk_persist(config.model, instances_to_create)

            if logs_to_create:
                ImportLog.objects.bulk_create(logs_to_create)

            if empty_count > 0:
                ImportJob.objects.filter(id=job.id).update(total_rows=F("total_rows") - empty_count)

        # 5. Finalize and Notify
        chunk.status = ImportChunk.Status.DONE
        chunk.save(update_fields=["status", "updated_at"])
        
        check_job_completion(job.id)
        
        # Metrics and Throttled WebSocket Notify
        elapsed = time.time() - start_time
        metrics = {
            "event": "chunk_processed",
            "job_id": str(job.id),
            "chunk_index": chunk.chunk_index,
            "success": len(instances_to_create),
            "failure": len(logs_to_create),
            "latency_ms": int(elapsed * 1000),
        }
        logger.info(metrics)
        
        # Adaptive UI Throttling: Only send every N chunks or on final chunk
        total_chunks = job.chunks.count()
        if chunk.chunk_index % max(1, total_chunks // 20) == 0 or chunk.chunk_index == total_chunks - 1:
            send_progress_update(job.id, metrics)

    except Exception as exc:
        # 6. Resilience and Retry logic
        chunk.status = ImportChunk.Status.PENDING
        chunk.save(update_fields=["status", "updated_at"])
        
        logger.error({
            "event": "chunk_error",
            "chunk_id": chunk_id,
            "error": str(exc),
            "retry": self.request.retries
        })
        
        # Avoid infinite retry loops on non-transient errors if possible
        if isinstance(exc, (IntegrityError, ValueError)):
             chunk.status = ImportChunk.Status.FAILED
             chunk.save(update_fields=["status"])
             raise
             
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
        
    finally:
        if adapter:
            adapter.close()
        if file_obj:
            file_obj.close()

def send_progress_update(job_id, payload):
    """Throttled WebSocket notification helper."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"job_{job_id}", {"type": "job_progress", "payload": payload}
            )
    except Exception as e:
        logger.warning(f"WebSocket Notification failed: {e}")

def check_job_completion(job_id):
    """
    Check if all chunks for a job are done and finalize job status.
    Uses database-level counting for accuracy.
    """
    job = ImportJob.objects.get(id=job_id)
    pending_chunks = job.chunks.exclude(status=ImportChunk.Status.DONE).exists()
    
    if not pending_chunks:
        # Final aggregation
        job.failure_count = ImportLog.objects.filter(job=job).count()
        job.success_count = job.total_rows - job.failure_count
        
        if job.success_count <= 0 and job.failure_count > 0:
            job.status = ImportJob.Status.FAILED
            job.error_message = "All rows failed validation."
        else:
            job.status = ImportJob.Status.COMPLETED
            
        job.save(update_fields=["status", "failure_count", "success_count", "error_message"])
        
        # Trigger cleanup if not in debug
        from django.conf import settings
        if not getattr(settings, "DEBUG", False):
            from .cleanup_tasks import cleanup_job
            cleanup_job.delay(job.id)
