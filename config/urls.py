# config/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Core application routes first so custom /admin/* views resolve before Django admin
    path("", include("core.urls")),

    # Django admin
    path("admin/", admin.site.urls),

    # Authentication (allauth or built-in)
    path("accounts/", include("allauth.urls")),  # or django.contrib.auth.urls if not using allauth
]


handler404 = "config.views.error_404"
handler500 = "config.views.error_500"
