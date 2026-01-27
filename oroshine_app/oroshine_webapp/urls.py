from django.urls import path, include, reverse_lazy
from django.contrib.auth import views as auth_views

from . import views
from .views import CustomPasswordResetView


urlpatterns = [
    # ==========================================
    # MONITORING
    # ==========================================
    path("metrics/", views.prometheus_metrics, name="prometheus-metrics"),

    # ==========================================
    # PUBLIC PAGES
    # ==========================================
    path("", views.homepage, name="home"),
    path("about/", views.about, name="about"),
    path("appointment/", views.appointment, name="appointment"),
    path("contact/", views.contact, name="contact"),
    path("price/", views.price, name="price"),
    path("service/", views.service, name="service"),
    path("team/", views.team, name="team"),
    path("testimonial/", views.testimonial, name="testimonial"),

    # ==========================================
    # USER
    # ==========================================
    path("profile/", views.user_profile, name="user_profile"),

    # ==========================================
    # AUTHENTICATION
    # ==========================================
    path("custom-register/", views.register_request, name="custom_register"),
    path("custom-login/", views.login_request, name="custom_login"),
    path("custom-logout/", views.logout_request, name="custom_logout"),

    # ==========================================
    # PASSWORD RESET (EMAIL FLOW – LOGGED OUT)
    # ==========================================
    # 1. Enter email
    path(
        "password-reset/",
        CustomPasswordResetView.as_view(
            template_name="password_reset.html"
        ),
        name="password_reset",
    ),

    # 2. Email sent page
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="password_reset_done.html"
        ),
        name="password_reset_done",
    ),

    # 3. Link from email → set new password
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),

    # 4. Password reset success
    path(
        "password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # ==========================================
    # PASSWORD CHANGE (LOGGED-IN USERS)
    # ==========================================
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="change_password.html",
            success_url=reverse_lazy("password_change_done"),
        ),
        name="change_password",
    ),

    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="change_password_done.html"
        ),
        name="password_change_done",
    ),

    # ==========================================
    # AJAX / API
    # ==========================================
    path("api/check-slots/", views.check_slots_ajax, name="check_slots_ajax"),
    path("api/check-availability/", views.check_availability, name="check_availability"),
]
