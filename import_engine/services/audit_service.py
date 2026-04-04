import json
import logging
import hashlib
from django.db import transaction
from django.utils import timezone
from import_engine.domain.models import ImportJob, ImportChunk

logger = logging.getLogger(__name__)


class SurgicalUndoService:
    """Handles precision rollbacks of specific chunks."""

    @classmethod
    @transaction.atomic
    def revert_chunk(cls, chunk_id: str) -> dict:
        """
        Surgically removes all records created by a specific chunk.
        """
        try:
            chunk = ImportChunk.objects.select_related("job").get(id=chunk_id)
            job = chunk.job
            config = None

            from import_engine.domain.config_registry import get_config

            config = get_config(job.model_name)

            if not config or not chunk.created_ids:
                return {"status": "skipped", "message": "No records to revert."}


            model = config.model
            count, _ = model.objects.filter(pk__in=chunk.created_ids).delete()


            chunk.created_ids = []
            chunk.status = ImportChunk.Status.FAILED
            chunk.save(update_fields=["created_ids", "status"])

            job.success_count = max(0, job.success_count - count)
            job.processed_rows = max(0, job.processed_rows - count)
            job.save(update_fields=["success_count", "processed_rows"])

            logger.warning(
                f"Surgical Undo: Reverted {count} rows for Chunk {chunk.chunk_index}"
            )
            return {"status": "success", "reverted_count": count}

        except Exception as e:
            logger.exception(f"Surgical Undo Failed for Chunk {chunk_id}: {e}")
            return {"status": "error", "message": str(e)}


class AuditTraceabilityService:
    """Generates signed audit logs for ingestion provenance."""

    @classmethod
    def generate_proof_of_ingestion(cls, job_id: str) -> str:
        """Generates a signed summary of ingestion provenance."""
        try:
            job = ImportJob.objects.get(id=job_id)


            provenance = {
                "job_id": str(job.id),
                "timestamp": timezone.now().isoformat(),
                "filename": job.original_filename,
                "fingerprint": job.file_fingerprint,
                "success_count": job.success_count,
                "failure_count": job.failure_count,
                "throughput": job.throughput_rows_sec,
                "model": job.model_name,
            }


            payload = json.dumps(provenance, sort_keys=True)
            from django.conf import settings

            key = getattr(settings, "SECRET_KEY", "unsecure")

            signature = hashlib.sha256(f"{payload}:{key}".encode()).hexdigest()

            proof = {
                "provenance": provenance,
                "signature": signature,
                "engine_version": "1.4.0",
            }


            return json.dumps(proof, indent=2)

        except Exception as e:
            logger.error(f"Audit Traceability Failed: {e}")
            return '{"error": "Failed to generate proof"}'
