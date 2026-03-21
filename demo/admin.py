from django.contrib import admin
from .models import Department, Role, Employee, Product

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('title', 'level')

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'email', 'department', 'role', 'joined_date')
    list_filter = ('department', 'role', 'is_active')
    search_fields = ('full_name', 'email')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'name', 'price', 'stock', 'is_available')
    list_filter = ('is_available',)
    search_fields = ('sku', 'name')
