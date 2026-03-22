from django.urls import path
from .views.upload_views import ImportUploadView, TemplateDownloadView
from .views.manage_views import JobStatusView, JobChunksView, JobLogsView

urlpatterns = [
    path(
        "imports/<str:model_name>/template/",
        TemplateDownloadView.as_view(),
        name="import_template",
    ),
    path(
        "imports/<str:model_name>/upload/",
        ImportUploadView.as_view(),
        name="import_upload",
    ),
    path("jobs/<uuid:job_id>/status/", JobStatusView.as_view(), name="job_status"),
    path("jobs/<uuid:job_id>/chunks/", JobChunksView.as_view(), name="job_chunks"),
    path("jobs/<uuid:job_id>/logs/", JobLogsView.as_view(), name="job_logs"),
]
