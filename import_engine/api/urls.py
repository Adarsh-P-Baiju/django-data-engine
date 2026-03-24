from django.urls import path
from .views.upload_views import ModelImportViewSet
from .views.manage_views import JobStatusView, JobChunksView, JobLogsView

urlpatterns = [
    path(
        "imports/<str:model_name>/template/",
        ModelImportViewSet.as_view({"get": "download_template"}),
        name="import_template",
    ),
    path(
        "imports/<str:model_name>/upload/",
        ModelImportViewSet.as_view({"post": "import_data"}),
        name="import_upload",
    ),
    path("jobs/<uuid:job_id>/status/", JobStatusView.as_view(), name="job_status"),
    path("jobs/<uuid:job_id>/chunks/", JobChunksView.as_view(), name="job_chunks"),
    path("jobs/<uuid:job_id>/logs/", JobLogsView.as_view(), name="job_logs"),
]
