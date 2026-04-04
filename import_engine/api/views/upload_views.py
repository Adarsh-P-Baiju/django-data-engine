from rest_framework import viewsets
from import_engine.api.mixins.core import ImportMixin


class ModelImportViewSet(ImportMixin, viewsets.GenericViewSet):
    """Polymorphic ViewSet for data ingestion into registered models."""


    def get_import_model_name(self):
        return self.kwargs.get("model_name")
