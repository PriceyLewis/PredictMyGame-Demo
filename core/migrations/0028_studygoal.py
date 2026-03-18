from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0027_plannedmodule_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudyGoal",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("academic", "Academic"),
                            ("assessment", "Assessment"),
                            ("habit", "Habit"),
                            ("application", "Application"),
                        ],
                        default="academic",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("planning", "Planning"),
                            ("active", "In Progress"),
                            ("completed", "Completed"),
                            ("paused", "Paused"),
                        ],
                        default="planning",
                        max_length=20,
                    ),
                ),
                ("due_date", models.DateField(blank=True, null=True)),
                ("target_percent", models.FloatField(blank=True, null=True)),
                ("progress", models.PositiveSmallIntegerField(default=0)),
                ("module_name", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="study_goals",
                        to="auth.user",
                    ),
                ),
            ],
            options={
                "ordering": ["status", "due_date", "-created_at"],
            },
        ),
    ]
