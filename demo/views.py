from rest_framework.views import APIView
from import_engine.api.mixins import ImportMixin
from drf_spectacular.utils import extend_schema


class EmployeeImportAPIView(ImportMixin, APIView):
    """
    Demonstration of wrapping the ViewSet ImportMixin into a standard DRF APIView.
    """

    import_model_name = "Employee"

    @extend_schema(summary="Upload Employee Data (APIView Version)")
    def post(self, request, *args, **kwargs):
        return self.import_data(request, *args, **kwargs)

    @extend_schema(summary="Download Employee Template (APIView Version)")
    def get(self, request, *args, **kwargs):
        return self.download_template(request, *args, **kwargs)
