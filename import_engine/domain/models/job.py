import uuid
from django.db import models


class ImportJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SCANNING = "SCANNING", "Scanning"
        CLEAN = "CLEAN", "Clean"
        INFECTED = "INFECTED", "Infected"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_name = models.CharField(max_length=100)
    file = models.FileField(upload_to="imports/pending/", null=True, blank=True)
    local_path = models.CharField(max_length=512, null=True, blank=True)
    status_message = models.TextField(null=True, blank=True)
    original_filename = models.CharField(max_length=255)
    file_fingerprint = models.CharField(max_length=64, db_index=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    total_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)

    field_mapping = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Job {self.id} ({self.status})"
