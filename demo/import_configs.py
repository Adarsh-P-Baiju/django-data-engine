from import_engine.domain.config_registry import BaseImportConfig, register_import
from .models import Employee, Department, Role, Product


@register_import("Department")
class DepartmentImportConfig(BaseImportConfig):
    model = Department
    fields = {
        "name": {"label": "Department Name", "rules": ["required"]},
        "code": {"label": "Dept Code", "rules": ["required"]},
        "is_active": {"label": "Active?", "rules": []},
    }


@register_import("Role")
class RoleImportConfig(BaseImportConfig):
    model = Role
    fields = {
        "title": {"label": "Job Title", "rules": ["required"]},
        "level": {"label": "Pay Level", "rules": ["required"]},
    }


@register_import("Employee")
class EmployeeImportConfig(BaseImportConfig):
    model = Employee
    conflict_resolution = "update"
    upsert_keys = ["email"]
    fields = {
        "full_name": {"label": "Full Name", "rules": ["required"]},
        "email": {
            "label": "Email Address",
            "rules": ["required", "email"],
            "pii": True,
        },
        "phone": {"label": "Phone Number", "rules": ["phone"], "pii": True},
        "age": {"label": "Age", "rules": ["required"]},
        "salary": {"label": "Annual Salary", "rules": ["required"], "pii": True},
        "rating": {"label": "Performance Rating", "rules": []},
        "is_active": {"label": "Currently Active", "rules": []},
        "joined_date": {"label": "Join Date", "rules": ["required"]},
        "department": {
            "label": "Department",
            "fk": "Department",
            "lookup": "name",
            "create_if_missing": True,
        },
        "role": {
            "label": "Rank/Role",
            "fk": "Role",
            "lookup": "title",
            "create_if_missing": True,
        },
        "notes": {"label": "Private Notes", "rules": [], "pii": True},
    }


@register_import("Product")
class ProductImportConfig(BaseImportConfig):
    model = Product
    fields = {
        "sku": {"label": "SKU/Part Number", "rules": ["required"]},
        "name": {"label": "Product Name", "rules": ["required"]},
        "price": {"label": "Unit Price", "rules": ["required"]},
        "stock": {"label": "Quantity in Stock", "rules": ["required"]},
    }
