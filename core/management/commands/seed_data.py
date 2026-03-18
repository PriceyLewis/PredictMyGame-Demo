from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import (
    Module, PredictionSnapshot, WeeklyStat, UserProfile,
    BugReport, Feedback
)
from django.utils import timezone
import random
from faker import Faker
from django.conf import settings
from core.ml import get_prediction_models

fake = Faker()

class Command(BaseCommand):
    help = "Seed the database with mock PredictMyGrade data and refresh adaptive models."

    def handle(self, *args, **kwargs):
        self.stdout.write("?? Seeding mock PredictMyGrade data...")

        users = []
        for i in range(5):
            user, _ = User.objects.get_or_create(
                username=f"student{i+1}",
                defaults={"email": f"student{i+1}@example.com"},
            )
            user.set_password("demo1234")
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.is_premium = random.choice([True, False])
            profile.save()
            users.append(user)

        levels = ["GCSE", "ALEVEL", "BTEC", "UNI"]
        for u in users:
            for _ in range(8):
                Module.objects.get_or_create(
                    user=u,
                    name=fake.catch_phrase()[:30],
                    level=random.choice(levels),
                    credits=random.choice([10, 15, 20, 30]),
                    grade_percent=round(random.uniform(40, 90), 2),
                )

        for u in users:
            for _ in range(3):
                PredictionSnapshot.objects.create(
                    user=u,
                    average_percent=random.uniform(50, 85),
                    created_at=timezone.now() - timezone.timedelta(days=random.randint(1, 30))
                )

        for i in range(6):
            week_date = timezone.now().date() - timezone.timedelta(weeks=i)
            WeeklyStat.objects.update_or_create(
                week_start=week_date,
                defaults={
                    "users": random.randint(10, 100),
                    "snapshots": random.randint(20, 200),
                },
            )

        for u in users:
            BugReport.objects.create(
                user=u,
                description=fake.sentence(),
                steps=fake.text(),
                status=random.choice(["New", "In Progress", "Resolved"]),
            )
            Feedback.objects.create(
                user=u,
                category=random.choice(["General", "Feature Suggestion"]),
                message=fake.text(max_nb_chars=100),
            )

        self.stdout.write("? Mock data seeded successfully.")

        self.stdout.write("?? Training adaptive prediction models...")
        models = get_prediction_models(force_retrain=True)
        if not models:
            self.stdout.write(self.style.ERROR("?? Failed to train adaptive models."))
        else:
            free_meta = models.get("free", {})
            premium_meta = models.get("premium", {})
            self.stdout.write(self.style.SUCCESS(
                f"? Free model ready (features={len(free_meta.get('features', []))}, rmse={free_meta.get('rmse', 0):.3f})"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"? Premium model ready (features={len(premium_meta.get('features', []))}, rmse={premium_meta.get('rmse', 0):.3f})"
            ))

        self.stdout.write(self.style.SUCCESS("?? PredictMyGrade seeding complete."))
