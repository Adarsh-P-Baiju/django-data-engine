from django.contrib import admin
from .domain.models import ImportJob, ImportChunk, ImportLog


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "model_name", "status", "created_at", "updated_at")
    list_filter = ("model_name", "status")
    search_fields = ("id", "model_name")


@admin.register(ImportChunk)
class ImportChunkAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "chunk_index", "status", "start_row", "end_row")
    list_filter = ("status",)
    search_fields = ("job__id",)


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "row_number", "is_fatal", "created_at")
    list_filter = ("is_fatal", "job__model_name")
    search_fields = ("job__id", "errors")
