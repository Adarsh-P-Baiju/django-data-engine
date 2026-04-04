# 🚀 Django Data Engine

An enterprise-grade, storage-agnostic data pipeline framework for Django. Transform complex CSV/Excel imports into a secure, asynchronous, and observable background process.

---

## 🛠️ Integration Setup Guide

Follow these exact steps to integrate the engine into your project.

### 1. Installation
Install the package from your local source or git repository:

```bash
pip install -e .
```

### 2. Django Configuration
Add `import_engine` to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    "rest_framework",
    "import_engine",
]
```

### 3. Database Alignment
Run the engine's migrations to initialize the tracking tables:

```bash
python manage.py migrate import_engine
```

### 4. Shared Storage Setup
The engine uses your project's `DEFAULT_FILE_STORAGE`. Ensure it is configured (e.g., S3, FileSystem, or MinIO).

---

## 🏗️ Celery Architecture & Task Registry

For the asynchronous pipeline to function, you must configure Celery correctly.

### 1. Define Celery Instance
Create or update `your_project/celery.py`:

```python
import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "your_project.settings")

app = Celery("your_project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

### 2. Project Initialization
Ensure Celery is loaded in `your_project/__init__.py`:

```python
from .celery import app as celery_app

__all__ = ("celery_app",)
```

### 3. Queue Definition (Optional)
By default, the engine uses the `heavy_tasks` queue. Listen to it in your worker:

```bash
celery -A your_project worker -Q heavy_tasks,default --loglevel=info
```

---

## ⚙️ Exhaustive Settings Reference

Override these in your project's `settings.py` for full control:

| Setting Key | Default Value | Description |
|---|---|---|
| `IMPORT_ENGINE_MAX_FILE_SIZE_MB` | `1024` | Maximum upload size in MB |
| `IMPORT_ENGINE_CLAMAV_HOST` | `"localhost"` | ClamAV daemon hostname |
| `IMPORT_ENGINE_CLAMAV_PORT` | `3310` | ClamAV daemon port |
| `IMPORT_ENGINE_CLAMAV_FAIL_SAFE` | `True` | Bypass scan if ClamAV is offline |
| `IMPORT_ENGINE_REGION_QUEUES` | `{"DEFAULT": "heavy_tasks"}` | Mapping of zones to Celery queues |

---

## 🔗 URL Routing & Entry Points

Include the engine routes in your main `urls.py`:

```python
from django.urls import path, include

urlpatterns = [
    path("api/engine/", include("import_engine.api.urls")),
]
```

---

## 🚀 Model Ingestion Configuration

Register your model with a configuration block in `apps.py` or a dedicated `imports.py`:

```python
from import_engine.domain.config_registry import ImportConfig, register_config
from myapp.models import Employee

register_config(ImportConfig(
    model=Employee,
    fields={
        "full_name":  {"label": "Employee Name", "rules": ["required"]},
        "email":      {"label": "Email", "rules": ["required", "email"]},
        "department": {"label": "Department", "fk": "Department", "lookup": "name"},
    }
))
```

---

## 📡 View Interface Options

### 1. REST Framework (API)
The engine provides high-performance endpoints:
- `POST /api/engine/imports/<model_name>/upload/`
- `GET /api/engine/imports/<model_name>/template/`

### 2. Standard Django (Forms/AJAX)
Universal Class-Based Views:
- `GET/POST /api/engine/standard/upload/<model_name>/`
- `GET /api/engine/standard/template/<model_name>/`
- `GET /api/engine/standard/status/<uuid:job_id>/`

---

## 📄 License
MIT
