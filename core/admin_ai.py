from django.contrib import admin, messages
from django.shortcuts import render
from django.core.management import call_command
from core.models import AIModelStatus

@admin.register(type("AIControl", (), {}))
class AIControlAdmin(admin.ModelAdmin):
    change_list_template = "admin/ai_control.html"

    def changelist_view(self, request, extra_context=None):
        ai_status = AIModelStatus.objects.first()
        if request.method == "POST" and "retrain_ai" in request.POST:
            call_command("retrain_ai")
            messages.success(request, "✅ AI retraining complete.")
            ai_status = AIModelStatus.objects.first()
        return render(request, "admin/ai_control.html", {"ai_status": ai_status})
