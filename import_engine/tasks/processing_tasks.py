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
    """Generates file segments for parallel processing."""
    try:
        generate_chunks_for_job(job_id)
    except Exception as exc:
        job = ImportJob.objects.get(id=job_id)
        job.status = ImportJob.Status.FAILED
        job.error_message = f"Orchestration Failed: {str(exc)}"
        job.save(update_fields=["status", "error_message"])
        logger.error(
            {"event": "orchestration_failed", "job_id": job_id, "error": str(exc)}
        )
        raise self.retry(exc=exc, countdown=10)


@shared_task(bind=True, max_retries=5)
def process_chunk(self, chunk_id):
    """Processes a specific file chunk with sub-batch persistence."""
    start_time = time.time()


    try:
        chunk = ImportChunk.objects.select_related("job").get(id=chunk_id)
        job = chunk.job
        config = get_config(job.model_name)

        if not config:
            chunk.status = ImportChunk.Status.FAILED
            chunk.save(update_fields=["status"])
            return


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
        empty_count = 0


        SUB_BATCH_SIZE = 500


        from import_engine.services.dedupe_service import DedupeService
        from import_engine.services.load_guard import LoadGuardService

        deduper = DedupeService(job.model_name)


        row_iterator = adapter.iter_rows(
            start_row=chunk.start_row, end_row=chunk.end_row
        )

        def process_batch(batch):
            if not batch:
                return 0, 0

            row_indices, row_dicts = zip(*batch)
            mapped_rows = [
                apply_mapping(rd, job.field_mapping, config) for rd in row_dicts
            ]


            resolver.prefetch(mapped_rows)

            batch_instances = []
            batch_staging = []
            batch_logs = []


            business_key_field = getattr(
                config, "business_key", next(iter(config.fields.keys()), "id")
            )

            for idx, (row_idx, row_dict, mapped_dict) in enumerate(
                zip(row_indices, row_dicts, mapped_rows)
            ):


                b_val = str(mapped_dict.get(business_key_field, ""))
                if b_val and deduper.is_duplicate(b_val):

                    batch_logs.append(
                        ImportLog(
                            job=job,
                            chunk=chunk,
                            row_number=row_idx,
                            row_data=mask_pii(row_dict, config),
                            errors={
                                "dedupe": "Row rejected as probable duplicate (Bloom Filter hit)."
                            },
                            is_fatal=False,
                        )
                    )
                    continue

                cleaned_data, errors = validate_row(config, mapped_dict)


                for fk_field, f_config in resolver.fk_fields.items():
                    val = mapped_dict.get(fk_field)
                    if val:
                        resolved_obj = resolver.resolve(fk_field, val)
                        if not resolved_obj:
                            if isinstance(f_config, dict) and f_config.get("required"):
                                errors[fk_field] = (
                                    f"Foreign key resolution failed for '{val}'"
                                )
                            else:
                                cleaned_data[fk_field] = None
                        else:
                            cleaned_data[fk_field] = resolved_obj


                LoadGuardService.throttle(factor=0.05)

                if errors:
                    batch_logs.append(
                        ImportLog(
                            job=job,
                            chunk=chunk,
                            row_number=row_idx,
                            row_data=mask_pii(row_dict, config),
                            errors=errors,
                            is_fatal=True,
                        )
                    )
                    from import_engine.domain.models import ImportStaging

                    batch_staging.append(
                        ImportStaging(
                            job=job,
                            row_number=row_idx,
                            raw_data=row_dict,
                            mapped_data=cleaned_data,
                            errors=errors,
                        )
                    )
                else:
                    if hasattr(config.model, "import_job"):
                        cleaned_data["import_job"] = job
                    batch_instances.append(config.model(**cleaned_data))


            with transaction.atomic():
                if batch_instances:
                    conflict_res = getattr(config, "conflict_resolution", "fail")
                    created_objs = []

                    if conflict_res == "update":
                        upsert_keys = getattr(config, "upsert_keys", [])
                        update_fields = [
                            f for f in config.fields.keys() if f not in upsert_keys
                        ]
                        created_objs = bulk_persist(
                            config.model,
                            batch_instances,
                            upsert_fields={
                                "unique_fields": upsert_keys,
                                "update_fields": update_fields,
                            },
                        )
                    elif conflict_res == "ignore":
                        created_objs = bulk_persist(
                            config.model, batch_instances, ignore_conflicts=True
                        )
                    else:
                        created_objs = bulk_persist(config.model, batch_instances)


                    if created_objs:

                        new_ids = [
                            str(obj.pk) for obj in created_objs if hasattr(obj, "pk")
                        ]
                        chunk.created_ids.extend(new_ids)
                        chunk.save(update_fields=["created_ids"])

                if batch_logs:
                    ImportLog.objects.bulk_create(batch_logs)
                if batch_staging:
                    from import_engine.domain.models import ImportStaging

                    ImportStaging.objects.bulk_create(
                        batch_staging, ignore_conflicts=True
                    )

            return len(batch_instances), len(batch_staging)

        total_success = 0
        total_failed = 0
        current_batch = []

        for row_idx, row_dict in row_iterator:
            if not any(
                v is not None and str(v).strip() != "" for v in row_dict.values()
            ):
                empty_count += 1
                continue

            current_batch.append((row_idx, row_dict))
            if len(current_batch) >= SUB_BATCH_SIZE:
                s, f = process_batch(current_batch)
                total_success += s
                total_failed += f
                current_batch = []

        if current_batch:
            s, f = process_batch(current_batch)
            total_success += s
            total_failed += f


        if chunk.chunk_index == 0:
            total_processed = total_success + total_failed
            if total_processed > 0:
                failure_rate = total_failed / total_processed
                threshold = getattr(config, "abort_threshold", 0.8)
                if failure_rate > threshold:
                    job.status = ImportJob.Status.FAILED
                    job.error_message = (
                        f"Sanity Check Failed: {int(failure_rate * 100)}% failure rate."
                    )
                    job.save(update_fields=["status", "error_message"])
                    raise ValueError(job.error_message)

        if empty_count > 0:
            ImportJob.objects.filter(id=job.id).update(
                total_rows=F("total_rows") - empty_count
            )


        elapsed = time.time() - start_time
        processed_in_this_chunk = total_success + total_failed


        from django.utils import timezone



        job.refresh_from_db(fields=["processed_rows", "total_rows", "started_at"])

        if not job.started_at:
            job.started_at = timezone.now()

        new_processed_total = job.processed_rows + processed_in_this_chunk
        remaining_rows = max(0, job.total_rows - new_processed_total)


        total_elapsed = (timezone.now() - job.started_at).total_seconds()
        avg_throughput = new_processed_total / max(total_elapsed, 0.001)
        eta_seconds = int(remaining_rows / avg_throughput) if avg_throughput > 0 else 0

        ImportJob.objects.filter(id=job.id).update(
            processed_rows=F("processed_rows") + processed_in_this_chunk,
            throughput_rows_sec=avg_throughput,
            estimated_remaining_seconds=eta_seconds,
            started_at=job.started_at,
        )

        chunk.status = ImportChunk.Status.DONE
        chunk.save(update_fields=["status", "updated_at"])

        check_job_completion(job.id)

        metrics = {
            "event": "chunk_processed",
            "job_id": str(job.id),
            "chunk_index": chunk.chunk_index,
            "success": total_success,
            "failure": total_failed,
            "latency_ms": int(elapsed * 1000),
            "rows_per_second": round(avg_throughput, 2),
            "eta_seconds": eta_seconds,
            "percent_complete": round((new_processed_total / job.total_rows) * 100, 2)
            if job.total_rows > 0
            else 0,
        }
        logger.info(metrics)


        total_chunks = job.chunks.count()
        if (
            chunk.chunk_index % max(1, total_chunks // 20) == 0
            or chunk.chunk_index == total_chunks - 1
        ):
            send_progress_update(job.id, metrics)

    except Exception as exc:

        chunk.status = ImportChunk.Status.PENDING
        chunk.save(update_fields=["status", "updated_at"])

        logger.error(
            {
                "event": "chunk_error",
                "chunk_id": chunk_id,
                "error": str(exc),
                "retry": self.request.retries,
            }
        )


        if isinstance(exc, (IntegrityError, ValueError)):
            chunk.status = ImportChunk.Status.FAILED
            chunk.save(update_fields=["status"])
            raise

        raise self.retry(exc=exc, countdown=2**self.request.retries)

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
    """Finalizes job status after all chunks are complete."""
    from django.utils import timezone
    from import_engine.services.diagnostic_service import DiagnosticService

    job = ImportJob.objects.get(id=job_id)
    pending_chunks = job.chunks.exclude(status=ImportChunk.Status.DONE).exists()

    if not pending_chunks:

        job.failure_count = ImportLog.objects.filter(job=job).count()
        job.success_count = job.total_rows - job.failure_count
        job.finished_at = timezone.now()

        if job.success_count <= 0 and job.failure_count > 0:
            job.status = ImportJob.Status.FAILED
            job.error_message = "All rows failed validation."
        else:
            job.status = ImportJob.Status.COMPLETED

        job.save(
            update_fields=[
                "status",
                "failure_count",
                "success_count",
                "error_message",
                "finished_at",
            ]
        )


        report = DiagnosticService.generate_report(str(job.id))
        summary_md = DiagnosticService.format_report_as_markdown(report)


        from import_engine.services.audit_service import AuditTraceabilityService

        proof_json = AuditTraceabilityService.generate_proof_of_ingestion(str(job.id))

        full_status = f"{summary_md}\n\nProof of Ingestion: {proof_json}"

        job.status_message = full_status
        job.save(update_fields=["status_message"])

        logger.info(
            f"Job {job.id} Finalized. Performance: {report['metrics']['avg_throughput_rows_sec']} rows/sec"
        )


        from django.conf import settings

        if not getattr(settings, "DEBUG", False):
            from .cleanup_tasks import cleanup_job

            cleanup_job.delay(job.id)
