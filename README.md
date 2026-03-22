# 🚀 Django Data Engine

An enterprise-grade, plug-and-play asynchronous data pipeline framework for Django REST Framework, powered by a fully-featured **Import Engine**.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Configuration DSL](#configuration-dsl)
- [API Reference](#api-reference)
- [WebSockets Progress](#websockets-progress)
- [Project Structure](#project-structure)
- [Infrastructure](#infrastructure)
- [Quick Start](#quick-start)
- [Makefile Commands](#makefile-commands)

---

## Overview

The **Django Data Engine Import Engine** allows you to plug-and-play enterprise-grade data imports into any Django REST Framework project. By simply registering your model with an `ImportConfig`, you instantly gain a secure, ClamAV-scanned, Celery-powered, chunked data import pipeline — with real-time WebSockets progress, smart fuzzy header mapping, FK resolution, row-level validation, and a Dead-Letter Queue for failures.

---

## Architecture

```
                 Upload (multipart/form-data)
                          │
               ┌──────────▼─────────────┐
               │     Rate Limiter       │  ← Per-user & Anon throttles
               │     File Validator     │  ← Size, MIME, Extension checks
               └──────────┬─────────────┘
                          │
               ┌──────────▼─────────────┐
               │   ClamAV Pre-Scanner   │  ← ephemeral /tmp/uploads volume
               └──────────┬─────────────┘
                  CLEAN   │   INFECTED → Rejected immediately
               ┌──────────▼─────────────┐
               │   MinIO Object Store   │  ← Persistent storage via S3 API
               └──────────┬─────────────┘
                          │
               ┌──────────▼─────────────┐
               │   Execution Engine     │  ← Reads headers → Fuzzy Mapper
               │   (Orchestrator)       │  ← Generates ImportChunk records
               └──────────┬─────────────┘
                          │
          ┌───────────────▼────────────────┐
          │         Celery Workers         │
          │   (heavy_tasks, 1000 rows/chunk)│
          │                                │
          │  For each chunk:               │
          │   → Stream rows from file      │
          │   → Fuzzy map headers          │
          │   → Validate via DSL rules     │
          │   → Resolve FK IDs in-memory   │
          │   → Bulk INSERT / UPSERT       │
          │   → Log failures to DLQ        │
          │   → Broadcast via WebSocket    │
          └───────────────┬────────────────┘
                          │
               ┌──────────▼─────────────┐
               │  Cleanup (light_tasks) │  ← Removes file from MinIO
               └────────────────────────┘
```

---

## Key Features

### 🔒 Security-First Pipeline
- **ClamAV Pre-Scan**: Before any file is persisted to MinIO, it passes through ClamAV mounted on an ephemeral shared Docker volume (`/tmp/uploads`). Infected files are immediately rejected and never touch storage.
- **File Validation**: MIME type, file extension, and file size are all checked at the API boundary before any further processing.
- **Rate Limiting**: `UploadUserRateThrottle` and `UploadAnonRateThrottle` prevent brute-force upload abuse.

### 🧠 Smart Fuzzy Header Mapping
- Powered by `thefuzz` and `python-Levenshtein`.
- Compares raw CSV/Excel column headers against your config field keys **and human-readable `label`s**.
- Exact matches are mapped first. Remaining headers with ≥85% Levenshtein similarity are automatically matched.
- The resolved mapping `dict` is stored on the `ImportJob.field_mapping` JSON field.
- Every Celery chunk worker then rewrites each incoming row dict using the resolved mapping before validation.

```
Raw headers:    ["Full Name", "Email Adress", "Dept"]
Config fields:  ["full_name", "email_address", "department"] (or their assigned labels)

Resolved:       { "Full Name" → "full_name", "Email Adress" → "email_address", "Dept" → "department" }
```

### ⚡ Chunked Celery Execution
- The Orchestrator streams the file using memory-safe adapters (no full load into RAM).
- `ImportChunk` records are created per 1,000-row block with `start_row` and `end_row`.
- Each chunk is dispatched independently to `celery_heavy` queue.
- Chunks track status (`PENDING`, `PROCESSING`, `DONE`, `FAILED`), retry counts and timing.
- Chunk workers retry up to 5 times with an exponential backoff (`5 × retry_count` seconds).

### 🔗 In-Memory FK Resolution
- `FKResolver` reads all FK field definitions from the config.
- Before processing any row in a chunk, **all related IDs are bulk-fetched into a Python dict in a single query**.
- This completely eliminates N+1 database queries even for files with complex FK relationships.

```python
# Example config with FK
"department": {"fk": "Department", "lookup": "name"}

# FKResolver pre-fetches:
{ "Engineering": 5, "Marketing": 12, "HR": 3 }
```

### 📋 Validation DSL
Define rules per field in your `ImportConfig`. The DSL interpreter applies them row-by-row:

| Rule | Description |
|---|---|
| `required` | Field must be present and non-empty |
| `email` | Must be a valid email address format |

### 📡 Real-Time WebSockets Progress
- The Django server runs in full **ASGI** mode via `daphne`.
- Clients subscribe to the job's progress channel:
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/engine/jobs/{job_id}/progress/");
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```
- Every successful chunk broadcasts:
```json
{
  "event": "chunk_processed",
  "job_id": "...",
  "chunk_index": 3,
  "success_count": 987,
  "failure_count": 13,
  "rows_per_sec": 4200.5,
  "latency_ms": 238
}
```
- Every chunk failure also broadcasts an `chunk_failed` event with the error, retry count, and chunk ID.

### 📬 Dead-Letter Queue (DLQ)
- Every row that fails validation or FK resolution generates an `ImportLog` record.
- Failures are stored with the original `row_data` dict and the exact `errors` dict.
- The `/jobs/{job_id}/logs/` endpoint exposes them in a paginated API for correction workflows.

### 🔁 Idempotency
- Every file is MD5-fingerprinted on upload.
- If the same file is re-uploaded while an active job exists, it is immediately rejected, preventing duplicate data.

### 📊 Smart Excel Template Generator
- `GET /api/engine/template/{model_name}/` returns a dynamically generated `.xlsx` file fully compatible with both Excel and Google Sheets.
- Extracted headers use the human-readable `label` parameter from your DSL config.
- Required fields are highlighted in red.
- **Dynamic Reference Dropdowns**: FK and Choice fields automatically query the database and embed up to 100 choices inside dedicated Reference Sheets (e.g. `Department Reference`).
- Bulletproof validation is implemented using **Named Ranges** to ensure dropdowns survive import into third-party tools like Google Sheets.
- Tooltips are embedded in header cells explaining field requirements.

### 🧹 Automatic Cleanup
- When all chunks of a job complete, `cleanup_job` is dispatched to the `light_tasks` queue.
- The source file is automatically deleted from MinIO after successful import.

---

## Configuration DSL

Register your model with the config registry in `import_engine/domain/config_registry.py`:

```python
from import_engine.domain.config_registry import ImportConfig, register_config
from myapp.models import Employee

register_config(ImportConfig(
    model=Employee,
    fields={
        "full_name":  {"label": "Employee Name", "rules": ["required"]},
        "email":      {"label": "Email", "rules": ["required", "email"]},
        "department": {"label": "Department", "fk": "Department", "lookup": "name"},
        "role":       {"label": "Rank / Role", "fk": "Role", "lookup": "title"},
    }
))
```

---

## API Reference

Swagger UI: `http://localhost:8000/api/docs/`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/engine/upload/{model_name}/` | Upload CSV/Excel file |
| `GET` | `/api/engine/template/{model_name}/` | Download Excel template |
| `GET` | `/api/engine/jobs/{job_id}/` | Poll job status |
| `GET` | `/api/engine/jobs/{job_id}/chunks/` | View chunk statuses |
| `GET` | `/api/engine/jobs/{job_id}/logs/?page=1` | View paginated row errors |

---

## WebSockets Progress

Connect your frontend to the live progress stream:

```
ws://localhost:8000/ws/engine/jobs/{job_id}/progress/
```

| Event | When |
|---|---|
| `chunk_processed` | Emitted after each successful chunk completion |
| `chunk_failed` | Emitted after each chunk failure (before retry) |

---

## Project Structure

```
import_engine/
├── api/
│   ├── views/
│   │   ├── upload_views.py    # ImportUploadView, TemplateDownloadView
│   │   └── manage_views.py    # JobStatusView, JobChunksView, JobLogsView
│   ├── file_validators/
│   │   ├── __init__.py
│   │   └── core.py            # Size, MIME, Extension checks
│   ├── mixins/
│   │   ├── __init__.py
│   │   └── core.py            # ImportMixin for ViewSets
│   ├── serializers/
│   │   ├── __init__.py        # Re-exports core serializers
│   │   └── core.py            # ImportJob, ImportChunk, ImportLog
│   ├── throttling/
│   │   ├── __init__.py
│   │   └── rates.py           # UploadUserRateThrottle, UploadAnonRateThrottle
│   └── urls.py
├── domain/
│   ├── models/
│   │   ├── job.py             # ImportJob (status, fingerprint, field_mapping)
│   │   ├── chunk.py           # ImportChunk (retries, start/end row, status)
│   │   └── log.py             # ImportLog (DLQ row failures)
│   └── config_registry.py     # ImportConfig + registration
├── execution_engine/
│   └── orchestrator.py        # Fuzzy mapping + chunk generation
├── parsing/
│   ├── base_adapter.py
│   ├── csv_adapter.py
│   ├── excel_adapter.py       # openpyxl read-only streaming
│   └── header_mapper.py       # thefuzz Levenshtein mapper
├── services/
│   ├── upload_service.py      # ClamAV scan + MinIO upload pipeline
│   ├── security_service.py
│   ├── persistence.py         # bulk_create + ON CONFLICT upsert
│   └── mapping/
│       └── fk_resolver.py     # In-memory FK bulk preloader
├── validators/
│   └── dsl.py                 # Rule interpreter + GDPR mutators
├── tasks/
│   ├── processing_tasks.py    # Celery chunk processing + WS broadcast
│   └── cleanup_tasks.py       # MinIO file deletion
├── websockets/
│   ├── consumers.py           # JobProgressConsumer
│   └── routing.py             # ws/ URL patterns
├── observability/
│   └── metrics.py             # Structured JSON logging formatter
└── utils/
    └── template_generator.py  # Excel template with dropdowns + highlights
```

---

## Infrastructure

| Service | Description | Port |
|---|---|---|
| `web` | Django + Daphne ASGI | `8000` |
| `celery_heavy` | Processing queue | — |
| `celery_light` | Cleanup queue | — |
| `db` | PostgreSQL 15 | `5444` |
| `redis` | Broker + Channels | `6379` |
| `minio` | Object storage | `9000 / 9001` |
| `clamav` | Antivirus daemon | `3310` |
| `flower` | Celery UI | `5555` |
| `adminer` | DB management UI | `8080` |

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/Adarsh-P-Baiju/django-data-engine.git
cd django-data-engine

# Configure environment
cp .env.example .env   # edit as needed

# Build and boot the full stack
make build

# Apply migrations
make migrate

# Create admin user
make superuser
```

---

## Makefile Commands

```bash
make up               # Start all containers
make down             # Stop containers
make down-volumes     # ⚠️ Wipe all data volumes
make build            # Rebuild images and start
make restart-workers  # Soft-restart Celery only
make logs             # Tail all container logs
make logs-web         # Django API logs only
make logs-worker      # Celery + Flower logs
make shell            # Bash inside web container
make dbshell          # PostgreSQL interactive shell
make redis-cli        # Redis CLI
make makemigrations   # Generate Django migrations
make migrate          # Apply migrations
make superuser        # Create Django admin
make test             # Run test suite
make format           # Auto-format with black
make lint             # Ruff linting
make pip-freeze       # Sync requirements.txt from container
```

---

## 📄 License

MIT
