

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("import_engine", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="importjob",
            name="field_mapping",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
