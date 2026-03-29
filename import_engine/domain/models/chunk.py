from django.db import models
from .job import ImportJob


class ImportChunk(models.Model):
    """Tracks a subset of rows for parallel processing."""
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        DONE = "DONE", "Done"
        FAILED = "FAILED", "Failed"

    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="chunks")
    chunk_index = models.IntegerField()
    start_row = models.IntegerField()
    end_row = models.IntegerField()

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    retry_count = models.IntegerField(default=0)
    
    created_ids = models.JSONField(
        default=list, 
        blank=True, 
        help_text="List of Primary Keys created by this chunk."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("job", "chunk_index")

    def __str__(self):
        return f"Chunk {self.chunk_index} for Job {self.job.id}"
