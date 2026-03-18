from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Module, AIModelStatus
from core.ml import get_prediction_models


class Command(BaseCommand):
    help = "Retrains the PredictMyGrade adaptive prediction models using current database data."

    def handle(self, *args, **kwargs):
        self.stdout.write("?? Starting adaptive model retraining...")

        if not Module.objects.exists():
            self.stdout.write(self.style.ERROR("?? No modules found  add data first (or generate mock data)."))
            return

        models = get_prediction_models(force_retrain=True)
        if not models:
            self.stdout.write(self.style.ERROR("?? Training failed  no samples produced."))
            return

        free_meta = models.get("free", {})
        premium_meta = models.get("premium", {})

        AIModelStatus.objects.all().delete()
        AIModelStatus.objects.create(
            last_retrained_at=timezone.now(),
            free_accuracy=round(free_meta.get("rmse") or 0, 3),
            premium_accuracy=round(premium_meta.get("rmse") or 0, 3),
        )

        free_features = len(free_meta.get("features", []))
        premium_features = len(premium_meta.get("features", []))

        self.stdout.write(
            self.style.SUCCESS(
                f"? Free model refreshed (features={free_features}, rmse={free_meta.get('rmse', 0):.3f})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"? Premium model refreshed (features={premium_features}, rmse={premium_meta.get('rmse', 0):.3f})"
            )
        )
        self.stdout.write(self.style.SUCCESS("?? Adaptive models cached successfully."))
