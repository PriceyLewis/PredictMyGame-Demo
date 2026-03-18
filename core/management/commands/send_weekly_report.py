from django.core.management.base import BaseCommand
from core.views import send_weekly_admin_report

class Command(BaseCommand):
    help = "Send the weekly PredictMyGrade admin analytics report."

    def handle(self, *args, **options):
        if send_weekly_admin_report():
            self.stdout.write(self.style.SUCCESS("✅ Weekly report sent successfully."))
        else:
            self.stdout.write(self.style.WARNING("⚠️ Weekly report skipped or failed."))
