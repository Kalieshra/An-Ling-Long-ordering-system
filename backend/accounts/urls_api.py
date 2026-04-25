"""Customer auth API. Other routes (refresh/logout/password-change) added in Task 6."""
from django.urls import path

from .views_api import LoginView, RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
]
