from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0033_dataexportlog"),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatsNewEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("summary", models.CharField(max_length=280)),
                ("body", models.TextField(blank=True)),
                (
                    "icon",
                    models.CharField(
                        blank=True,
                        help_text="Optional emoji or short label shown before the entry title.",
                        max_length=16,
                    ),
                ),
                (
                    "display_order",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Lower numbers appear first.",
                    ),
                ),
                ("is_published", models.BooleanField(default=True)),
                ("published_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "What's new entry",
                "verbose_name_plural": "What's new entries",
                "ordering": ["display_order", "-published_at", "-created_at"],
            },
        ),
    ]
