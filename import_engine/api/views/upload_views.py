from rest_framework import viewsets
from import_engine.api.mixins.core import ImportMixin

class ModelImportViewSet(ImportMixin, viewsets.GenericViewSet):
    """
    Ultra-advanced Polymorphic ViewSet for importing data into any registered model.
    The model name is extracted automatically from the URL path, providing 
    a clean and unified interface for all data ingestion tasks.
    """
    # Overriding mixin method to support URL-based model resolution
    def get_import_model_name(self):
        return self.kwargs.get("model_name")

    # Inherits import_data (POST /import) and download_template (GET /import/template) from ImportMixin
