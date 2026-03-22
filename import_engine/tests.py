from unittest.mock import patch
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError

from import_engine.services.upload_service import handle_upload
from import_engine.domain.models import ImportJob
from import_engine.domain.config_registry import register_import, BaseImportConfig
from django.db import models


class DummyModel(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "import_engine"


@register_import("Dummy")
class DummyConfig(BaseImportConfig):
    model = DummyModel
    fields = {"name": ["required"]}


class PipelineTests(TestCase):
    @patch("import_engine.services.security_service.VirusScanner.scan_file")
    @patch("import_engine.execution_engine.orchestrator.dispatch_import_job")
    def test_clean_file_upload(self, mock_dispatch, mock_scan):
        mock_scan.return_value = (True, None)  # Clean file

        csv_content = b"name\nAlice\nBob\n"
        uploaded = SimpleUploadedFile("clean.csv", csv_content, content_type="text/csv")

        job = handle_upload("Dummy", uploaded)

        self.assertEqual(job.status, ImportJob.Status.PENDING)
        self.assertTrue(job.file.name.endswith("clean.csv"))
        mock_dispatch.assert_called_once_with(job.id)

    @patch("import_engine.services.security_service.VirusScanner.scan_file")
    def test_infected_file_upload_rejected(self, mock_scan):
        mock_scan.return_value = (False, "EICAR-Test-Signature")  # Infected

        csv_content = (
            b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        )
        uploaded = SimpleUploadedFile("virus.csv", csv_content, content_type="text/csv")

        with self.assertRaises(ValidationError) as ctx:
            handle_upload("Dummy", uploaded)

        self.assertIn("Security Alert", str(ctx.exception))
        self.assertIn("EICAR", str(ctx.exception))
