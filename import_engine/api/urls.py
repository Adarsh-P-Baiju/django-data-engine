from django.urls import path
from rest_framework.routers import DefaultRouter
from .views.upload_views import ModelImportViewSet
from .views.manage_views import ImportJobViewSet
from .views.upload_resumable import ResumableUploadView
from import_engine.views.monitor import TestReportListView, TestReportDetailView
from import_engine.views.core import (
    ImportUploadView,
    TemplateDownloadView,
    ImportJobStatusView,
)

router = DefaultRouter()
router.register(r"jobs", ImportJobViewSet, basename="job")

urlpatterns = [

    path(
        "standard/upload/<str:model_name>/",
        ImportUploadView.as_view(),
        name="import_standard_upload",
    ),
    path(
        "standard/template/<str:model_name>/",
        TemplateDownloadView.as_view(),
        name="import_standard_template",
    ),
    path(
        "standard/status/<uuid:job_id>/",
        ImportJobStatusView.as_view(),
        name="import_job_status",
    ),

    path(
        "monitor/reports/",
        TestReportListView.as_view(),
        name="monitor-reports",
    ),
    path(
        "monitor/reports/<str:report_name>/",
        TestReportDetailView.as_view(),
        name="monitor-report-detail",
    ),

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
    path(
        "imports/resumable/<str:model_name>/init/",
        ResumableUploadView.as_view(),
        name="import_resumable_init",
    ),
    path(
        "imports/resumable/<str:job_id>/",
        ResumableUploadView.as_view(),
        name="import_resumable_chunk",
    ),
] + router.urls
