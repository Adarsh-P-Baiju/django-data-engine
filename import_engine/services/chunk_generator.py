import os
import logging

from django.db import transaction
from import_engine.domain.models import ImportJob, ImportChunk
from import_engine.parsing.csv_adapter import CSVAdapter
from import_engine.parsing.excel_adapter import ExcelAdapter
from import_engine.domain.config_registry import get_config
from import_engine.services.header_mapper import generate_fuzzy_mapping

logger = logging.getLogger(__name__)


@transaction.atomic
def generate_chunks_for_job(job_id: str, chunk_size: int = 1000) -> int:
    """Generates segment records for parallel processing."""
    job = ImportJob.objects.select_for_update().get(id=job_id)
    file_obj = job.file.open("rb")

    ext = os.path.splitext(job.original_filename)[1].lower()
    adapter = None

    try:
        if ext == ".csv":
            adapter = CSVAdapter(file_obj)
        elif ext in [".xlsx", ".xls"]:
            adapter = ExcelAdapter(file_obj)
        else:
            raise ValueError(f"Unsupported extension {ext}")

        config = get_config(job.model_name)
        if config:
            raw_headers = adapter.get_headers()
            job.field_mapping = generate_fuzzy_mapping(raw_headers, config.fields)
            job.save(update_fields=["field_mapping"])
            logger.info(f"Chunk Generator: Generated header mapping for Job {job.id}")

        chunk_index = 0
        if ext == ".csv":
            # Fast streaming line count for 100M rows
            adapter.file_obj.seek(0)
            # Count lines without loading into memory
            total_rows = sum(1 for _ in adapter.file_obj) - 1  # Subtract 1 for header
            adapter.file_obj.seek(0)
            # Re-read header to advance DictReader/Iterator past it
            next(adapter.file_obj)

            num_chunks = (total_rows + chunk_size - 1) // chunk_size
            for idx in range(num_chunks):
                start_row = (idx * chunk_size) + 1
                end_row = min(start_row + chunk_size - 1, total_rows)
                chunk = ImportChunk.objects.create(
                    job=job,
                    chunk_index=idx,
                    start_row=start_row,
                    end_row=end_row,
                    status=ImportChunk.Status.PENDING,
                )
                from import_engine.tasks.processing_tasks import process_chunk

                process_chunk.apply_async(args=[chunk.id], queue="light_tasks")
            chunk_index = num_chunks
        else:
            # For Excel
            for _ in adapter.chunked_read(chunk_size=chunk_size):
                start_row = (chunk_index * chunk_size) + 1
                end_row = start_row + chunk_size - 1
                chunk = ImportChunk.objects.create(
                    job=job,
                    chunk_index=chunk_index,
                    start_row=start_row,
                    end_row=end_row,
                    status=ImportChunk.Status.PENDING,
                )
                from import_engine.tasks.processing_tasks import process_chunk

                process_chunk.apply_async(args=[chunk.id], queue="light_tasks")
                chunk_index += 1
            total_rows = chunk_index * chunk_size
        job.save(update_fields=["total_rows"])

        return chunk_index

    finally:
        if adapter:
            adapter.close()
        file_obj.close()
