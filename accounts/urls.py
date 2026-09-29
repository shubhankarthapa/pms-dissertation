from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import AccountPasswordChangeForm, LoginForm


app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            form_class=LoginForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="accounts/password_change.html",
            form_class=AccountPasswordChangeForm,
            success_url=reverse_lazy("accounts:profile"),
        ),
        name="password_change",
    ),
]