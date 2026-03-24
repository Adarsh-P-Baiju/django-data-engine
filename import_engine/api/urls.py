from django.urls import path
from rest_framework.routers import DefaultRouter
from .views.upload_views import ModelImportViewSet
from .views.manage_views import ImportJobViewSet
from import_engine.views.monitor import TestReportListView, TestReportDetailView

router = DefaultRouter()
router.register(r"jobs", ImportJobViewSet, basename="job")

urlpatterns = [
    # Premium Diagnostic Monitor (Native Django Views)
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
    
    # Import Endpoints
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
] + router.urls
