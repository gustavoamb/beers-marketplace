import os
import json
import requests
from uuid import uuid4
from copy import deepcopy

import stripe

from django.db import transaction
from django.db.models import Q
from django.shortcuts import render
from django.contrib.sites.shortcuts import get_current_site

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.parsers import BaseParser

from stores.models import Purchase

from payments.models import (
    Funding,
    RechargeFundsSession,
    StoreFundAccount,
    StorePayment,
    Movement,
)
from payments.serializers import (
    FundingSerializer,
    MovementSerializer,
    StoreFundAccountSerializer,
    StorePaymentSerializer,
)

from common.permissions import IsAdminOrVerifiedStoreUser, IsVerifiedStoreUser
from common.payments.services.stripe import stripe_service
from common.payments.services.paypal import paypal_service
from common.payments.services.paypal import OrderError as PaypalOrderError
from common.payments.services.mercantil import MercantilService
from common.payments.interfaces.payment_information import (
    PaymentInformation,
    TransactionCapture,
)

from common.views import get_store_id_from_request

from .api.validate_order import PrePurchaseValidator
from .api.fulfill_orders import (
    StripeOrderHandler,
    PaypalOrderHandler,
    MercantilOrderHandler,
)

import logging

logger = logging.getLogger("payment_views")


# Create your views here.
class FundingViewSet(viewsets.ModelViewSet):
    queryset = Funding.objects.all()
    serializer_class = FundingSerializer


class CreateStripeCheckoutSession(APIView):
    def post(self, request):
        try:
            customer_stripe_id = request.user.stripe_id
            product_price_id = request.data.get("product_price_id")
            product_quantity = request.data.get("product_quantity")
            domain = get_current_site(request).domain
            payload = {
                "customer": customer_stripe_id,
                "product_price_id": product_price_id,
                "product_quantity": product_quantity,
                "domain": domain,
            }
            checkout_session = stripe_service.create_payment_legacy(payload)
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"checkoutUrl": checkout_session.url}, status=status.HTTP_200_OK
        )


class RechargeViaStripeView(APIView):
    def post(self, request):
        user = request.user
        amount = request.data.get("amount")
        if float(amount) < 20:
            return Response(
                {"amount": "Monto mínimo de recarga: 20.0"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sessions_in_progress = RechargeFundsSession.objects.filter(
            user=user.id, status=RechargeFundsSession.Status.IN_PROGRESS
        )
        if not sessions_in_progress.exists():
            idempotency_key = str(uuid4())
            payment_information = PaymentInformation(
                amount=amount,
                external_customer_id=user.stripe_id,
                idempotency_key=idempotency_key,
            )
            with transaction.atomic():
                payment_intent = stripe_service.create_payment(payment_information)
                session = RechargeFundsSession.objects.create(
                    user=user,
                    payment_platform=Funding.PaymentPlatform.STRIPE,
                    order=payment_intent.id,
                    request_idempotency_key=idempotency_key,
                )
        else:
            session = sessions_in_progress.latest("updated_at")
            payment_information = PaymentInformation(
                amount=amount,
                external_customer_id=user.stripe_id,
            )
            payment_intent = stripe_service.update_payment(
                session.order, payment_information
            )

        stripe_fee = stripe_service.get_payment_fee(amount)

        response = {
            "payment_intent": payment_intent,
            "session_id": session.id,
            "stripe_fee": stripe_fee,
        }
        return Response(response, status=status.HTTP_200_OK)


class StripeWebhook(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            payment_intent = stripe_service.capture_payment(request)
        except ValueError as e:
            # Invalid payload
            logger.error(f"Stripe webhook error: {str(e)}")
            return Response(
                {"message": "Invalid payload"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except stripe_service._client.error.SignatureVerificationError as e:
            # Invalid signature
            logger.error(f"Stripe webhook error: {str(e)}")
            return Response(
                {"message": "Invalid payload signature"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment_intent is None:
            logger.info("PaymentIntent has not succeeded yet")
            return Response(status=status.HTTP_200_OK)

        stripe_handler = StripeOrderHandler(stripe_service, payment_intent)
        stripe_handler.fulfill_order()

        return Response(
            {"message": "Stripe webhook event processed"},
            status=status.HTTP_201_CREATED,
        )


class StripeSetupIntents(APIView):
    def post(self, request):
        try:
            user = request.user
            setup_intent = stripe_service.create_setup_intent(user.stripe_id)
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        response = {
            "customer_stripe_id": setup_intent.customer,
            "setup_intent_client_secret": setup_intent.client_secret,
        }
        return Response(response, status=status.HTTP_200_OK)

    def get(self, request):
        try:
            user = request.user
            setup_intents = stripe_service.list_customer_setup_intents(user.stripe_id)
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(setup_intents, status=status.HTTP_200_OK)


class StripeSetupIntentsConfirm(APIView):
    def get(self, request):
        try:
            setup_intent_id = request.data.get("setup_intent")
            setup_intent = stripe_service.confirm_setup_intent(setup_intent_id)
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(setup_intent, status=status.HTTP_200_OK)


class StripePaymentMethods(APIView):
    def get(self, request):
        try:
            user = request.user
            payment_methods = stripe_service.list_customer_payment_methods(
                user.stripe_id
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(payment_methods, status=status.HTTP_200_OK)


class StripePaymentMethodDetail(APIView):
    def get(self, request, payment_method_id):
        try:
            user = request.user
            payment_method = stripe_service.retrieve_customer_payment_method(
                user.stripe_id, payment_method_id
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(payment_method, status=status.HTTP_200_OK)

    def patch(self, request, payment_method_id):
        try:
            user = request.user
            payment_method = stripe_service.retrieve_customer_payment_method(
                user.stripe_id, payment_method_id
            )
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(payment_method, status=status.HTTP_200_OK)

    def delete(self, request, payment_method_id):
        try:
            stripe_service.detach_payment_method(payment_method_id)
        except Exception as e:
            return Response(
                {"message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {"message": "Payment method successfully detached from customer"},
            status=status.HTTP_200_OK,
        )


class CreatePaypalCheckout(APIView):
    def post(self, request):
        PAYPAL_APP_CLIENT_ID = os.getenv("PAYPAL_APP_CLIENT_ID")
        beers_purchase_amount = request.data.get("product_quantity")
        current_domain = get_current_site(request).domain
        user = request.user
        return render(
            request,
            "paypal_checkout.html",
            {
                "paypal_app_client_id": PAYPAL_APP_CLIENT_ID,
                "customer_id": user.id,
                "product_value": beers_purchase_amount,
                "beers_paypal_orders_url": f"http://{current_domain}/beers/paypal/orders",
            },
        )


class PlainTextParser(BaseParser):
    media_type = "text/plain;charset=UTF-8"

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Simply return a string representing the body of the request.
        """
        return stream.read()


class CreatePaypalOrderView(APIView):
    permission_classes = [AllowAny]
    parser_classes = (PlainTextParser,)

    def post(self, request):
        json_data = json.loads(request.data)
        beers_purchase_amount = json_data.get("product_quantity")
        payment_info = PaymentInformation(
            amount=beers_purchase_amount, external_customer_id=1
        )
        order = paypal_service.create_payment(payment_info)
        return Response(order, status=status.HTTP_200_OK)


class CapturePaypalOrderView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, paypal_order_id=None, *args, **kwargs):
        transaction = TransactionCapture(paypal_order_id)
        try:
            capture = paypal_service.capture_payment(transaction)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY:
                raise e

            order = paypal_service.show_order_details(transaction.id)
            paypal_handler = PaypalOrderHandler(order)
            order_error = PaypalOrderError(e.response.json())
            funding = paypal_handler.handle_payment_failure(order_error)
            return Response([funding], status=status.HTTP_201_CREATED)

        paypal_handler = PaypalOrderHandler(capture)
        fundings = paypal_handler.fulfill_order()
        return Response(fundings, status=status.HTTP_201_CREATED)


class ValidateOrderView(APIView):
    def post(self, request):
        store = request.data.get("store")
        products = request.data.get("products")
        promotions = request.data.get("promotions")
        user = request.user

        try:
            validator = PrePurchaseValidator(user, store, products, promotions)
            response = validator.validate_order()
        except Exception as e:
            return Response(
                {"message": f"Order validation failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(response, status=status.HTTP_200_OK)


class MovementsView(viewsets.ReadOnlyModelViewSet):
    serializer_class = MovementSerializer

    def get_queryset(self):
        user = self.request.user

        user_fundings = Q(funding__user=user)

        is_gift_sent = Q(movement_type=Movement.Type.GIFT_SENT)
        is_gift_accepted = Q(movement_type=Movement.Type.GIFT_ACCEPTED)
        is_gift_claimed = Q(movement_type=Movement.Type.GIFT_CLAIMED)
        is_gift_received = Q(movement_type=Movement.Type.GIFT_RECEIVED)
        is_other_gift_movement = Q(
            movement_type__in=[
                Movement.Type.GIFT_REJECTED,
                Movement.Type.GIFT_EXPIRED,
            ]
        )

        is_sender = Q(purchase__user=user)
        is_recipient = Q(purchase__gift_recipient=user)

        user_as_gift_sender = (
            is_gift_sent | is_gift_accepted | is_other_gift_movement
        ) & is_sender
        user_as_gift_recipient = (
            is_gift_claimed | is_other_gift_movement
        ) & is_recipient
        main_filter = user_fundings | user_as_gift_sender | user_as_gift_recipient

        gift_accepted_received_only = self.request.query_params.get(
            "gift_accepted_received_only", False
        )
        if gift_accepted_received_only:
            is_pending_gift_received = is_gift_received & Q(
                purchase__status=Purchase.Status.PENDING
            )
            is_not_gift_delivered = ~Q(
                purchase__status=Purchase.Status.DELIVERED
            )
            main_filter = (is_pending_gift_received | is_gift_accepted) & is_recipient &  is_not_gift_delivered

        return Movement.objects.filter(main_filter).order_by("-created_at")


class RechargeFundsSessionConfirmView(APIView):
    def post(self, request, session_id):
        session = RechargeFundsSession.objects.get(
            pk=session_id, status=RechargeFundsSession.Status.IN_PROGRESS
        )
        payment_intent_id = session.order
        payment_method_id = request.data.get("payment_method_id")

        with transaction.atomic():
            try:
                confirmed_payment_intent = stripe_service.confirm_payment(
                    payment_intent_id, payment_method_id
                )
            except stripe.error.StripeError as e:
                payment_intent = stripe_service.get_payment(payment_intent_id)
                stripe_handler = StripeOrderHandler(stripe_service, payment_intent)
                stripe_handler.handle_payment_failure(e.user_message)

                session.status = RechargeFundsSession.Status.COMPLETED
                session.save()

                return Response(
                    {"message": e.user_message}, status=status.HTTP_400_BAD_REQUEST
                )

            session.status = RechargeFundsSession.Status.COMPLETED
            session.save()

        return Response(confirmed_payment_intent, status=status.HTTP_200_OK)


class ConfirmMercantilMobilePaymentView(APIView):
    def post(self, request):
        customer = request.user
        search_parameters = deepcopy(request.data)
        mercantil_service = MercantilService()
        payments = mercantil_service.list_mobile_payments(filters=search_parameters)
        if not payments.transactions:
            mercantil_handler = MercantilOrderHandler(search_parameters, customer.id)
            funding = mercantil_handler.handle_payment_failure(
                payments.error_messages()
            )
            return Response(
                funding,
                status=status.HTTP_404_NOT_FOUND,
            )

        mercantil_handler = MercantilOrderHandler(payments.transactions[0], customer.id)
        funding = mercantil_handler.handle_funding()

        return Response(funding, status=status.HTTP_201_CREATED)


class StoreFundAccountViewSet(viewsets.ModelViewSet):
    queryset = StoreFundAccount.objects.all()
    serializer_class = StoreFundAccountSerializer
    permission_classes = (IsVerifiedStoreUser,)

    def get_queryset(self):
        queryset = self.queryset
        store_id = self.request.user.store.id
        return queryset.filter(store=store_id)

    def perform_create(self, serializer):
        serializer.save(store=self.request.user.store)

    def create(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        account_type = request.data.get("type", None)
        if account_type != StoreFundAccount.Type.VES:
            existing_ves_acc = queryset.filter(type=StoreFundAccount.Type.VES).exists()
            if not existing_ves_acc:
                return Response(
                    {
                        "type": "At least one (1) VES account must exist before creating other account types"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        is_preferential = request.data.get("is_preferential", False)
        if is_preferential:
            existing_preferential = queryset.filter(is_preferential=True).exists()
            if existing_preferential:
                return Response(
                    {
                        "is_preferential": "An Store can only have one (1) account set as preferential"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        is_preferential = request.data.get("is_preferential", False)
        if is_preferential:
            queryset = self.get_queryset()
            existing_preferential = queryset.filter(is_preferential=True).exists()
            if existing_preferential:
                return Response(
                    {
                        "is_preferential": "An Store can only have one (1) account set as preferential"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        account = queryset.get(pk=kwargs.get("pk"))
        if account.type == StoreFundAccount.Type.VES:
            is_last_ves_acc = (
                queryset.filter(type=StoreFundAccount.Type.VES).count() == 1
            )
            if is_last_ves_acc:
                return Response(
                    {
                        "message": "Could not delete the specified account because it's the last VES account remaining"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return super().destroy(request, *args, **kwargs)


class StorePaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StorePayment.objects.all()
    serializer_class = StorePaymentSerializer

    def get_queryset(self):
        queryset = self.queryset
        store_id = get_store_id_from_request(self.request)
        if store_id is not None:
            queryset = queryset.filter(store_id=store_id)

        payment_id = self.request.query_params.get("id")
        if payment_id is not None:
            queryset = queryset.filter(pk__startswith=payment_id)

        return queryset

    def get_permissions(self):
        admin_only_actions = ["create", "partial_update"]
        if self.action in admin_only_actions:
            return [IsAdminUser()]

        return [IsAdminOrVerifiedStoreUser()]
