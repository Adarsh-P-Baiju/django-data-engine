# 🚀 Django Data Engine

An enterprise-grade, highly scalable asynchronous data pipeline and ETL framework for Django REST Framework.

Built to securely handle massive ingestion workloads via Celery parallel execution, real-time WebSockets progress tracking, strict B2B Multi-Tenant architectural isolation, active GDPR Data Anonymizers, and robust streaming-memory parsers.

---

### Features currently included in the core:

* **Config-Driven DSL**: Declare your fields with standard directives (`["required", "email", "mask_email"]`).
* **Scan-Before-Save**: Every file is safely intercepted into ClamAV isolated ephemeral volumes before touching MinIO persistent storage.
* **Celery Chunks**: Massive files are automatically streamed, chunked into blocks of 1,000 rows, and executed in complete parallel. 
* **Real-time WebSockets**: Django Channels `ASGI` backend instantly multiplexes progress bars and error states back to frontend clients.
* **Data Guarantee**: Full Database Transaction atomicity, Idempotent fingerprints, and automated chunk-level retry queues.
* **Dead-Letter Queue (DLQ)**: Every single row failure instantly generates a paginated log metric containing the exact dictionary and validation error so your users can correct failures.
