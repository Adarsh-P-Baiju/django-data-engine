from django.urls import path
from rest_framework.routers import DefaultRouter
from .views.upload_views import ModelImportViewSet
from .views.manage_views import ImportJobViewSet

router = DefaultRouter()
router.register(r"jobs", ImportJobViewSet, basename="job")

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
] + router.urls
