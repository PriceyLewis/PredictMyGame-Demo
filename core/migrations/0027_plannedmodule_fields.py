from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0026_smartinsight_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="plannedmodule",
            name="category",
            field=models.CharField(
                choices=[("Core", "Core"), ("Elective", "Elective"), ("Optional", "Optional")],
                default="Core",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="plannedmodule",
            name="status",
            field=models.CharField(
                choices=[
                    ("Planned", "Planned"),
                    ("Enrolled", "Enrolled"),
                    ("In Progress", "In Progress"),
                    ("Completed", "Completed"),
                ],
                default="Planned",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="plannedmodule",
            name="term",
            field=models.CharField(
                choices=[
                    ("Term 1", "Term 1"),
                    ("Term 2", "Term 2"),
                    ("Term 3", "Term 3"),
                    ("Semester 1", "Semester 1"),
                    ("Semester 2", "Semester 2"),
                    ("Year-long", "Year-long"),
                ],
                default="Term 1",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="plannedmodule",
            name="workload_hours",
            field=models.DecimalField(decimal_places=1, default=0, max_digits=5),
        ),
    ]
