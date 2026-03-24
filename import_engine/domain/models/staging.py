from django.db import models
from .job import ImportJob

class ImportStaging(models.Model):
    """
    Enterprise Staging Table for Interactive Conflict Resolution.
    Stores rows that failed validation or require manual review.
    """
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="staging_rows")
    row_number = models.IntegerField()
    raw_data = models.JSONField(help_text="Original row data from the file.")
    mapped_data = models.JSONField(help_text="Data after header mapping applied.")
    errors = models.JSONField(help_text="Validation error messages.")
    
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("job", "row_number")
        verbose_name_plural = "Import Staging Rows"

    def __str__(self):
        return f"Staging Row {self.row_number} for Job {self.job.id}"
