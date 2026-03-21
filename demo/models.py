import uuid
from django.db import models

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    is_active = models.BooleanField(default=True)
    def __str__(self): return self.name

class Role(models.Model):
    title = models.CharField(max_length=100, unique=True)
    level = models.IntegerField(default=1)
    def __str__(self): return self.title

class Employee(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    age = models.IntegerField()
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    rating = models.FloatField(default=0.0)
    is_active = models.BooleanField(default=True)
    joined_date = models.DateField()
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.full_name

class Product(models.Model):
    sku = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name
