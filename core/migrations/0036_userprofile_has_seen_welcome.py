from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_module_is_sample_plannedmodule_is_sample_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="has_seen_welcome",
            field=models.BooleanField(default=False),
        ),
    ]
