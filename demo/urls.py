from django.urls import path
from .views import EmployeeImportAPIView

urlpatterns = [
    path("employee/import/", EmployeeImportAPIView.as_view(), name="employee-import"),
]
