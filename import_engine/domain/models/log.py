from django.db import models
from .job import ImportJob
from .chunk import ImportChunk


class ImportLog(models.Model):
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="logs")
    chunk = models.ForeignKey(
        ImportChunk, on_delete=models.SET_NULL, null=True, related_name="logs"
    )

    row_number = models.IntegerField()
    row_data = models.JSONField()
    errors = models.JSONField()

    is_fatal = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log for row {self.row_number} (Job {self.job.id})"
