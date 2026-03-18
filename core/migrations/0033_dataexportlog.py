from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0032_ucasoffer_enhancements"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DataExportLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "format",
                    models.CharField(
                        choices=[("json", "JSON"), ("csv", "CSV")],
                        default="json",
                        max_length=12,
                    ),
                ),
                ("record_count", models.PositiveIntegerField(default=0)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_export_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Data export",
                "verbose_name_plural": "Data exports",
                "ordering": ["-created_at"],
            },
        ),
    ]
