from hashids import Hashids

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from knox.views import LoginView as KnoxLoginView
from knox.auth import TokenAuthentication

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny

from common.permissions import IsPersonOrVerifiedStore
from common.money_exchange.dolar_venezuela import usd_exchange_rate_service

from users.models import User

hashids = Hashids(salt=settings.SECRET_KEY)


class LoginView(KnoxLoginView):
    # Override Knox's LoginView so it uses Basic Auth as indicated in
    # https://james1345.github.io/django-rest-knox/auth/#global-usage-on-all-views.
    authentication_classes = [BasicAuthentication]
    permission_classes = [IsPersonOrVerifiedStore]


def get_store_id_from_request(request):
    store_id = None
    user = request.user
    if user.is_staff:
        store_id = request.query_params.get("store", None)
    else:
        store_id = user.store.id

    return store_id


class ResetPasswordRequestToken(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data["email"]
        user = User.objects.get(email=email)

        token_generator = PasswordResetTokenGenerator()
        pwd_reset_token = token_generator.make_token(user=user)
        # send an e-mail to the user
        user_id = hashids.encode(user.id)
        context = {
            "username": user.username,
            "token": f"{user_id}/{pwd_reset_token}",
        }

        # render email text
        email_html_message = render_to_string(
            "password_recovery/password_recovery.html", context
        )
        email_plaintext_message = render_to_string(
            "password_recovery/password_recovery.txt", context
        )

        msg = EmailMultiAlternatives(
            # title:
            "Beers - Reinicio de contraseña",
            # message:
            email_plaintext_message,
            # from:
            settings.EMAIL_HOST_USER,
            # to:
            [user.email],
        )
        msg.attach_alternative(email_html_message, "text/html")
        msg.send()

        return Response({"message": "Recovery email sent"}, status=status.HTTP_200_OK)


class ResetPasswordConfirm(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        full_token = request.data.get("token")
        encoded_id, token = full_token.split("/")
        user_id = hashids.decode(encoded_id)[0]
        user = User.objects.get(id=user_id)

        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user=user, token=token):
            return Response(
                {"message": "Token is invalid or has expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        password = request.data.get("password")
        confirm_password = request.data.get("confirm_password")
        if password != confirm_password:
            return Response(
                {"message": "Passwords do not match"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save()

        return Response(
            {"message": "Password succesfully reset"}, status=status.HTTP_200_OK
        )


class ResetPasswordValidateToken(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        full_token = request.data.get("token")
        encoded_id, token = full_token.split("/")
        user_id = hashids.decode(encoded_id)[0]
        user = User.objects.get(id=user_id)

        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user=user, token=token):
            return Response(
                {"message": "Token is invalid or has expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"message": "Token is valid"}, status=status.HTTP_200_OK)


class USDToLocalCurrencyExchangeRate(APIView):
    def get(self, request):
        usd_exchange_rate = usd_exchange_rate_service.get_usd_exchange_rate()
        return Response({"usd_price": usd_exchange_rate}, status=status.HTTP_200_OK)


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response("OK", status=status.HTTP_200_OK)
