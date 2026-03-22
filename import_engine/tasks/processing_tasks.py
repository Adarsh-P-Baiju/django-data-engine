import time
import os
import logging
from celery import shared_task
from django.db import transaction

from import_engine.domain.models import ImportJob, ImportChunk, ImportLog
from import_engine.domain.config_registry import get_config
from import_engine.services.mapping.fk_resolver import FKResolver
from import_engine.validators.dsl import validate_row
from import_engine.services.persistence import bulk_persist
from import_engine.parsing.csv_adapter import CSVAdapter
from import_engine.parsing.excel_adapter import ExcelAdapter

logger = logging.getLogger('import_engine.metrics')

@shared_task(bind=True, max_retries=3)
def orchestrate_job(self, job_id):
    """
    Background job execution delegating to orchestrator logic.
    """
    from import_engine.execution_engine.orchestrator import generate_chunks_for_job
    try:
        generate_chunks_for_job(job_id)
    except Exception as exc:
        job = ImportJob.objects.get(id=job_id)
        job.status = ImportJob.Status.FAILED
        job.error_message = str(exc)
        job.save()
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=5)
def process_chunk(self, chunk_id):
    """
    Parses, validates, resolves FKs, and persists a specific chunk.
    Records granular logs (DLQ) and emits JSON structured metrics.
    """
    start_time = time.time()
    
    chunk = ImportChunk.objects.select_related('job').get(id=chunk_id)
    job = chunk.job
    config = get_config(job.model_name)
    
    if not config:
        chunk.status = ImportChunk.Status.FAILED
        chunk.save()
        return
        
    chunk.status = ImportChunk.Status.PROCESSING
    chunk.save(update_fields=['status', 'updated_at'])
    
    file_obj = job.file.open('rb')
    ext = os.path.splitext(job.original_filename)[1].lower()
    
    if ext == '.csv':
        adapter = CSVAdapter(file_obj)
    elif ext in ['.xlsx', '.xls']:
        adapter = ExcelAdapter(file_obj)
        
    resolver = FKResolver(config)
    
    logs_to_create = []
    instances_to_create = []
    
    try:
        rows_data = []
        empty_count = 0
        for row_idx, row_dict in adapter.iter_rows(start_row=chunk.start_row, end_row=chunk.end_row):
            # Check if entirely empty (all values None or whitespace)
            if not any(v is not None and str(v).strip() != '' for v in row_dict.values()):
                empty_count += 1
                continue
            rows_data.append((row_idx, row_dict))
            
        if empty_count > 0:
            from django.db.models import F
            job.total_rows = F('total_rows') - empty_count
            job.save(update_fields=['total_rows'])
            job.refresh_from_db(fields=['total_rows'])
            
        # Normalize headers via mapping or auto-mapping BEFORE prefetching
        mapped_rows_data = []
        for row_idx, row_dict in rows_data:
            if job.field_mapping:
                mapped_dict = {}
                for raw_key, raw_val in row_dict.items():
                    if raw_key in job.field_mapping:
                        mapped_dict[job.field_mapping[raw_key]] = raw_val
                row_dict = mapped_dict
            else:
                auto_mapped = {}
                label_to_field = {
                    (f_config.get('label') if isinstance(f_config, dict) else f_name): f_name
                    for f_name, f_config in config.fields.items()
                }
                for raw_key, raw_val in row_dict.items():
                    target = label_to_field.get(raw_key, raw_key)
                    auto_mapped[target] = raw_val
                row_dict = auto_mapped
            mapped_rows_data.append((row_idx, row_dict))

        rows_data = mapped_rows_data
        raw_dicts = [rd for idx, rd in rows_data]
        resolver.prefetch(raw_dicts)
        
        model_class = config.model
        
        for row_idx, row_dict in rows_data:
            cleaned_data, errors = validate_row(config, row_dict)
            
            for fk_field, f_config in resolver.fk_fields.items():
                val = row_dict.get(fk_field)
                if val:
                    resolved_obj = resolver.resolve(fk_field, val)
                    if not resolved_obj:
                        rules = f_config.get('rules', []) if isinstance(f_config, dict) else []
                        is_required = ('required' in rules) or (isinstance(f_config, dict) and f_config.get('required'))
                        
                        if is_required:
                            errors[fk_field] = f"Could not resolve FK for '{val}'"
                        else:
                            # Not required; gracefully neglect the missing FK
                            cleaned_data.pop(fk_field, None)
                            cleaned_data[fk_field] = None
                    else:
                        cleaned_data[fk_field] = resolved_obj
                        
            if errors:
                # Obfuscate PII before logging to DB
                safe_row_data = dict(row_dict)
                for f_name, f_config in config.fields.items():
                    if isinstance(f_config, dict) and f_config.get('pii'):
                        label = f_config.get('label', f_name)
                        if label in safe_row_data:
                            safe_row_data[label] = "*** MASKED ***"

                logs_to_create.append(ImportLog(
                    job=job,
                    chunk=chunk,
                    row_number=row_idx,
                    row_data=safe_row_data,
                    errors=errors,
                    is_fatal=True
                ))
            else:
                if 'department' in cleaned_data:
                    logger.error(f"STRANGE: department still in cleaned_data! keys={list(cleaned_data.keys())}, fk_fields={list(resolver.fk_fields.keys())}")
                instances_to_create.append(model_class(**cleaned_data))
                
        with transaction.atomic():
            if instances_to_create:
                conflict_res = getattr(config, 'conflict_resolution', 'fail')
                if conflict_res == 'update':
                    upsert_keys = getattr(config, 'upsert_keys', []) or []
                    # Everything not an upsert key is an update field
                    update_fields = [f for f in config.fields.keys() if f not in upsert_keys]
                    upsert_fields = {
                        'unique_fields': upsert_keys,
                        'update_fields': update_fields
                    }
                    bulk_persist(model_class, instances_to_create, upsert_fields=upsert_fields)
                elif conflict_res == 'ignore':
                    bulk_persist(model_class, instances_to_create, ignore_conflicts=True)
                else:
                    bulk_persist(model_class, instances_to_create)
                
            if logs_to_create:
                ImportLog.objects.bulk_create(logs_to_create)
                
        chunk.status = ImportChunk.Status.DONE
        chunk.save()
        
        check_job_completion(job.id)
        
        elapsed = time.time() - start_time
        rows_sec = len(rows_data) / elapsed if elapsed > 0 else 0
        payload = {
            "event": "chunk_processed",
            "job_id": str(job.id),
            "chunk_index": chunk.chunk_index,
            "success_count": len(instances_to_create),
            "failure_count": len(logs_to_create),
            "rows_per_sec": rows_sec,
            "latency_ms": int(elapsed * 1000)
        }
        logger.info(payload)
        
        # Debounce the WebSocket emitting to every 5th chunk (or the final chunk) to prevent ASGI overhead on huge files
        total_chunks = job.chunks.count()
        if chunk.chunk_index % 5 == 0 or chunk.chunk_index == (total_chunks - 1) or total_chunks < 10:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"job_{job.id}",
                    {"type": "job_progress", "payload": payload}
                )
            except Exception as e:
                logger.error(f"Channels Failed: {e}")
        
    except Exception as exc:
        chunk.retry_count += 1
        chunk.status = ImportChunk.Status.PENDING
        chunk.save()
        err_payload = {
            "event": "chunk_failed",
            "chunk_id": str(chunk.id),
            "error": str(exc),
            "retry_count": chunk.retry_count
        }
        logger.error(err_payload)
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"job_{job.id}",
                {"type": "job_progress", "payload": err_payload}
            )
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=5 * chunk.retry_count)
    finally:
        adapter.close()
        file_obj.close()


def check_job_completion(job_id):
    job = ImportJob.objects.prefetch_related('chunks').get(id=job_id)
    chunks = list(job.chunks.all())
    
    if all(c.status == ImportChunk.Status.DONE for c in chunks):
        job.failure_count = ImportLog.objects.filter(job=job).count()
        job.success_count = job.total_rows - job.failure_count
        
        if job.failure_count > 0 and job.success_count == 0:
            job.status = ImportJob.Status.FAILED
            job.error_message = f"All {job.failure_count} rows failed import validation."
        else:
            job.status = ImportJob.Status.COMPLETED
            
        job.save()
        
        from django.conf import settings
        if not getattr(settings, 'DEBUG', False):
            from .cleanup_tasks import cleanup_job
            cleanup_job.delay(job.id)
