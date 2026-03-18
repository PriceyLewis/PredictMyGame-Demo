from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect


def _should_return_json(request) -> bool:
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return True
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return True
    content_type = request.content_type or ""
    if "application/json" in content_type:
        return True
    return False


def premium_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")

        if request.user.is_staff:
            return view_func(request, *args, **kwargs)

        profile = getattr(request.user, "profile", None)
        if not profile or not profile.has_premium_access:
            message = "Upgrade to Premium to unlock this feature."
            if _should_return_json(request):
                return JsonResponse({"ok": False, "error": message}, status=403)
            messages.warning(request, message)
            return redirect("core:upgrade")

        return view_func(request, *args, **kwargs)

    return wrapper
