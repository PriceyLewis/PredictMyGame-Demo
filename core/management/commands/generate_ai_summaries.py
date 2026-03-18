from django.core.management.base import BaseCommand
from django.db.models import Avg
from django.contrib.auth.models import User
from core.models import PredictionHistory, AIInsightSummary

class Command(BaseCommand):
    help = "Generates weekly AI insight summaries for premium users"

    def handle(self, *args, **kwargs):
        premium_users = User.objects.filter(userprofile__is_premium=True)
        if not premium_users.exists():
            self.stdout.write("No premium users found.")
            return

        for user in premium_users:
            preds = PredictionHistory.objects.filter(user=user)
            if preds.count() < 3:
                continue  # skip if not enough data

            data = preds.aggregate(
                avg_eng=Avg("engagement_score"),
                avg_diff=Avg("difficulty_index"),
                avg_var=Avg("performance_variance"),
                avg_pred=Avg("predicted_average")
            )

            eng, diff, var, pred = data["avg_eng"], data["avg_diff"], data["avg_var"], data["avg_pred"]

            insights = []
            # Engagement analysis
            if eng > 0.7:
                insights.append("High engagement correlates with strong academic performance.")
            elif eng > 0.4:
                insights.append("Engagement is moderate; consistent effort could raise results.")
            else:
                insights.append("Low engagement appears to be a limiting factor in outcomes.")

            # Difficulty & performance
            if diff > 0.6 and pred >= 65:
                insights.append("Excellent performance maintained under high difficulty levels.")
            elif diff > 0.6 and pred < 60:
                insights.append("Challenging modules may be suppressing average performance.")
            elif diff < 0.3:
                insights.append("Modules are relatively easier, contributing to stable results.")

            # Variance
            if var > 0.5:
                insights.append("High variance detected; focus on achieving consistency.")
            else:
                insights.append("Low variance across modules — performance remains stable.")

            # Overall trend
            if pred >= 70:
                insights.append("Overall performance indicates First-class potential.")
            elif pred >= 60:
                insights.append("Strong 2:1 trajectory — keep up the momentum.")
            elif pred >= 50:
                insights.append("Currently on track for a 2:2; improvement possible with consistency.")
            else:
                insights.append("Below passing threshold — intensive support may help recovery.")

            summary = " ".join(insights)

            AIInsightSummary.objects.create(
                user=user,
                summary_text=summary,
                average_engagement=eng,
                average_difficulty=diff,
                average_variance=var,
                average_predicted=pred,
            )

            self.stdout.write(self.style.SUCCESS(f"Generated weekly summary for {user.username}"))
