from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_aichatsession_messages"),
    ]

    operations = [
        migrations.AddField(
            model_name="smartinsight",
            name="impact_score",
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name="smartinsight",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="smartinsight",
            name="title",
            field=models.CharField(blank=True, max_length=160),
        ),
    ]
