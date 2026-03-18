import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("predictmygrade")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Ensure beat schedule declared in settings is picked up automatically.
app.conf.beat_schedule = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
app.conf.timezone = getattr(settings, "TIME_ZONE", "UTC")


@app.task(bind=True)
def debug_task(self):
    print(f"Celery debug request: {self.request!r}")
