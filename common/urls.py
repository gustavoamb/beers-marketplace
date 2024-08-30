from django.urls import path
from knox import views as knox_views

from .views import (
    LoginView,
    ResetPasswordRequestToken,
    ResetPasswordValidateToken,
    ResetPasswordConfirm,
    USDToLocalCurrencyExchangeRate,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="knox_login"),
    path("auth/logout/", knox_views.LogoutView.as_view(), name="knox_logout"),
    path("auth/logout/all/", knox_views.LogoutAllView.as_view(), name="knox_logoutall"),
    path(
        r"auth/password-reset/",
        ResetPasswordRequestToken.as_view(),
        name="password_reset_request",
    ),
    path(
        r"auth/password-reset/validate-token/",
        ResetPasswordValidateToken.as_view(),
        name="password_reset_validate",
    ),
    path(
        r"auth/password-reset/confirm/",
        ResetPasswordConfirm.as_view(),
        name="password_reset_confirm",
    ),
    path(
        r"currency/usd-exchange/",
        USDToLocalCurrencyExchangeRate.as_view(),
        name="usd_exchange_rate",
    ),
]
