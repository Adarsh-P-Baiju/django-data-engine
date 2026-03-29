from django.test import TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from import_engine.domain.models import ImportJob, ImportLog


class BaseImportTestCase(TransactionTestCase):
    """Base class for Import Engine tests providing common utilities."""

    def create_test_file(
        self, content: str, filename: str = "test.csv"
    ) -> SimpleUploadedFile:
        return SimpleUploadedFile(
            filename, content.encode("utf-8"), content_type="text/csv"
        )

    def assertJobStatus(self, job_id, expected_status):
        job = ImportJob.objects.get(id=job_id)
        self.assertEqual(
            job.status,
            expected_status,
            f"Job {job_id} expected status {expected_status}, got {job.status}",
        )

    def assertLogCount(self, job_id, expected_count):
        count = ImportLog.objects.filter(job_id=job_id).count()
        self.assertEqual(
            count,
            expected_count,
            f"Job {job_id} expected {expected_count} logs, got {count}",
        )
