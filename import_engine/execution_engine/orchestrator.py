import os
from import_engine.domain.models import ImportJob, ImportChunk
from import_engine.parsing.csv_adapter import CSVAdapter
from import_engine.parsing.excel_adapter import ExcelAdapter


def dispatch_import_job(job_id):
    """
    Triggers the Celery pipeline to process the file in chunks.
    """
    from import_engine.tasks.processing_tasks import orchestrate_job

    orchestrate_job.delay(job_id)


def generate_chunks_for_job(job_id: str, chunk_size: int = 1000):
    """
    Reads the file using streaming adapters and generates ImportChunk records.
    Dispatches each chunk to parallel workers.
    """
    job = ImportJob.objects.get(id=job_id)
    file_obj = job.file.open("rb")

    ext = os.path.splitext(job.original_filename)[1].lower()
    if ext == ".csv":
        adapter = CSVAdapter(file_obj)
    elif ext in [".xlsx", ".xls"]:
        adapter = ExcelAdapter(file_obj)
    else:
        file_obj.close()
        raise ValueError(f"Unsupported extension {ext}")
    from import_engine.domain.config_registry import get_config
    from import_engine.parsing.header_mapper import generate_fuzzy_mapping

    config = get_config(job.model_name)
    if config:
        raw_headers = adapter.get_headers()
        job.field_mapping = generate_fuzzy_mapping(raw_headers, config.fields)
        job.save(update_fields=["field_mapping"])

    try:
        chunk_index = 0
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

            process_chunk.delay(chunk.id)

            chunk_index += 1

        job.total_rows = chunk_index * chunk_size
        job.save(update_fields=["total_rows"])

    finally:
        adapter.close()
