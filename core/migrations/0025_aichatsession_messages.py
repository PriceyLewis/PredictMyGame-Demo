from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0024_userprofile_trial_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="ai_persona",
            field=models.CharField(
                choices=[
                    ("mentor", "Friendly Mentor"),
                    ("coach", "Academic Coach"),
                    ("analyst", "Data Analyst"),
                ],
                default="mentor",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="AIChatSession",
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
                ("persona", models.CharField(choices=[("mentor", "Friendly Mentor"), ("coach", "Academic Coach"), ("analyst", "Data Analyst")], default="mentor", max_length=20)),
                ("title", models.CharField(blank=True, max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ai_chat_sessions", to="auth.user"),
                ),
            ],
            options={
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="AIChatMessage",
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
                ("role", models.CharField(choices=[("user", "User"), ("assistant", "Assistant"), ("system", "System")], max_length=12)),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="core.aichatsession"),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
    ]
