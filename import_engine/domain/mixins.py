from django.db import models
from import_engine.domain.models import ImportJob

class ImportedModelMixin(models.Model):
    """
    Mixin for models that are imported via the Import Engine.
    Provides data lineage and rollback capabilities.
    """
    import_job = models.ForeignKey(
        ImportJob, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="%(class)s_related",
        db_index=True,
        help_text="The import job that created or last updated this record."
    )
    imported_at = models.DateTimeField(
        auto_now_add=True, 
        null=True, 
        blank=True,
        help_text="Timestamp of the initial import."
    )

    class Meta:
        abstract = True
