from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_aiinsightfeedback"),
    ]

    operations = [
        migrations.AddField(
            model_name="ucasoffer",
            name="decision_type",
            field=models.CharField(
                choices=[
                    ("conditional", "Conditional"),
                    ("unconditional", "Unconditional"),
                    ("insurance", "Insurance (safety)"),
                ],
                default="conditional",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="ucasoffer",
            name="deadline",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ucasoffer",
            name="target_points",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
