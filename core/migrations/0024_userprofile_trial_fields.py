from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_userprofile_stripe_customer_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="trial_cancelled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="trial_ends_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="trial_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
