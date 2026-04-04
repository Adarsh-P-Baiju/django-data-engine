

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("import_engine", "0004_importstaging"),
    ]

    operations = [
        migrations.AddField(
            model_name="importchunk",
            name="created_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="List of Primary Keys created by this chunk.",
            ),
        ),
        migrations.AddField(
            model_name="importjob",
            name="estimated_remaining_seconds",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="importjob",
            name="finished_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="importjob",
            name="local_path",
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
        migrations.AddField(
            model_name="importjob",
            name="processed_bytes",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="importjob",
            name="started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="importjob",
            name="status_message",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="importjob",
            name="throughput_rows_sec",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="importjob",
            name="total_bytes",
            field=models.BigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="importchunk",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("PROCESSING", "Processing"),
                    ("DONE", "Done"),
                    ("FAILED", "Failed"),
                ],
                db_index=True,
                default="PENDING",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="importjob",
            name="file",
            field=models.FileField(blank=True, null=True, upload_to="imports/pending/"),
        ),
    ]
