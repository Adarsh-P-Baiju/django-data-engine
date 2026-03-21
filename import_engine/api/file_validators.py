import os
from django.core.exceptions import ValidationError
from django.conf import settings

def validate_file_size(file):
    max_size_mb = getattr(settings, 'IMPORT_MAX_FILE_SIZE_MB', 50)
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"File size exceeds the {max_size_mb}MB limit.")

def validate_file_extension(file):
    valid_extensions = getattr(settings, 'IMPORT_ALLOWED_EXTENSIONS', ['.csv', '.xlsx'])
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in valid_extensions:
        raise ValidationError(f"Unsupported file extension {ext}. Allowed: {valid_extensions}")
