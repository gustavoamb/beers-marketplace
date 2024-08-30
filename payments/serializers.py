from mimetypes import guess_type
from decimal import Decimal
from datetime import datetime
from pytz import timezone

import stripe

from django.db import transaction
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from rest_framework import serializers

from payments.models import (
    Funding,
    StoreFundAccount,
    StorePayment,
    Movement,
)
from stores.models import Purchase, PurchaseHasProduct, PurchaseHasPromotion
from stores.serializers import PurchaseSerializer

from stores.api.store_balance import calculate_store_balance

from administration.models import FundAccount

from common.utils import round_to_fixed_exponent
from common.serializers import DynamicFieldsModelSerializer
from common.money_exchange.dolar_venezuela import usd_exchange_rate_service


class FundingSerializer(serializers.ModelSerializer):
    movement_type = serializers.SerializerMethodField(read_only=True)
    payment_method = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Funding
        fields = [
            "id",
            "user",
            "amount",
            "purchased_via",
            "status",
            "reference",
            "fee",
            "total_amount",
            "payment_method",
            "movement_type",
            "error",
            "usd_exchange_rate",
            "created_at",
            "updated_at",
        ]

    def get_movement_type(self, obj):
        return "funding"

    def get_payment_method(self, obj):
        if obj.purchased_via == Funding.PaymentPlatform.STRIPE:
            stripe_payment_intent_id = obj.reference
            stripe_payment_intent = stripe.PaymentIntent.retrieve(
                stripe_payment_intent_id, expand=["payment_method"]
            )
            payment_method = stripe_payment_intent.payment_method
            if payment_method and payment_method.type == "card":
                return {"card": f"**** **** **** {payment_method.card.last4}"}
        elif obj.purchased_via == Funding.PaymentPlatform.PAYPAL:
            payment_method = "Paypal Funds"
        elif obj.purchased_via == Funding.PaymentPlatform.MERCANTIL_PAGO_MOVIL:
            payment_method = "Mercantil Pago Movil Funds"

        return payment_method

    def create(self, validated_data):
        with transaction.atomic():
            funding = super().create(validated_data)
            movement_data = {
                "movement_type": Movement.Type.FUNDING.value,
                "funding": funding.id,
                "grouping_id": Movement.objects.get_next_grouping_id(),
            }
            movement_serializer = MovementSerializer(data=movement_data)
            movement_serializer.is_valid(raise_exception=True)
            movement_serializer.save()
            return funding


class MovementsSerializer(serializers.Serializer):
    purchases = PurchaseSerializer(many=True)
    fundings = FundingSerializer(many=True)

    class Meta:
        read_only_fields = ["purchases", "fundings"]


class StoreFundAccountSerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = StoreFundAccount
        fields = [
            "id",
            "store",
            "type",
            "number",
            "holder_name",
            "bank_name",
            "doc_number",
            "doc_type",
            "phone",
            "is_preferential",
        ]
        read_only_fields = ["store"]

    def validate(self, data):
        acc_type = data["type"]
        missing = []
        if acc_type == StoreFundAccount.Type.VES:
            req_fields = [
                "number",
                "holder_name",
                "bank_name",
                "doc_type",
                "doc_number",
            ]
        elif acc_type == StoreFundAccount.Type.USD:
            req_fields = ["number", "holder_name", "bank_name"]
        elif acc_type == StoreFundAccount.Type.MOBILE_PAY:
            req_fields = [
                "phone",
                "bank_name",
                "doc_type",
                "doc_number",
            ]
        elif acc_type == StoreFundAccount.Type.PAYPAL:
            req_fields = ["holder_name"]

        missing = [field for field in req_fields if field not in data.keys()]
        if len(missing) > 0:
            msgs = [{field: f"This field is required" for field in missing}]
            error = {f"{acc_type}_fields": msgs}
            raise serializers.ValidationError(error)

        return data


class StorePaymentPurchaseSerializer(serializers.ModelSerializer):
    products = serializers.SerializerMethodField(read_only=True)
    promotions = serializers.SerializerMethodField(read_only=True)
    gift_recipient = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Purchase
        fields = [
            "id",
            "amount",
            "gift_recipient",
            "commission_amount",
            "products",
            "promotions",
        ]
        read_only_fields = ["gift_recipient", "products"]

    def get_gift_recipient(self, obj):
        return {
            "id": obj.gift_recipient.id,
            "name": obj.gift_recipient.profile.name,
        }

    def get_products(self, obj):
        purchases_products = (
            PurchaseHasProduct.objects.filter(purchase=obj.pk)
            .values("product")
            .distinct()
            .values("product", "product__name", "quantity")
        )
        return purchases_products

    def get_promotions(self, obj):
        purchases_products = (
            PurchaseHasPromotion.objects.filter(purchase=obj.pk)
            .values("promotion")
            .distinct()
            .values("promotion", "promotion__title", "quantity", "promotion__price")
        )
        return purchases_products


class StorePaymentSerializer(serializers.ModelSerializer):
    store_name = serializers.SerializerMethodField(read_only=True)
    purchases = StorePaymentPurchaseSerializer(many=True)

    class Meta:
        model = StorePayment
        fields = [
            "id",
            "store",
            "store_name",
            "amount",
            "reference_number",
            "receipt",
            "funds_account_origin",
            "usd_exchange_rate",
            "created_at",
            "updated_at",
            "purchases",
        ]
        read_only_fields = [
            "products",
            "promotions",
            "store_name",
            "purchases",
            "reference_number",
        ]

    def get_store_name(self, obj):
        return obj.store.name

    def validate(self, data):
        if self.instance:
            # We're updating an instance, for now only the 'receipt'
            # field is gonna be allowed to be updated.
            data.pop("store", None)
            return data

        amount = round_to_fixed_exponent(data["amount"])
        fund_account = data.get("funds_account_origin")
        acc_balance = fund_account.balance
        if fund_account.currency == FundAccount.Currency.VES:
            usd_rate = data.get("usd_exchange_rate")
            acc_balance /= usd_rate

        if acc_balance < abs(amount):
            raise serializers.ValidationError(
                {
                    "amount_&_funds_account_origin": "Insufficient balance in origin fund account to perform operation."
                }
            )

        store = data["store"]
        balances_by_store = calculate_store_balance(store.id)
        store_balance = balances_by_store.get(store=store.id)

        amount_owed = round_to_fixed_exponent(store_balance.balance)
        if amount != amount_owed:
            raise serializers.ValidationError(
                {
                    "amount": f"Amount provided does not match the current owed amount for Store {store.id}"
                }
            )

        data["purchases"] = [p.id for p in store_balance.unpaid_purchases]

        return data

    def create(self, validated_data):
        purchases_ids = validated_data.pop("purchases")
        with transaction.atomic():
            store_payment = super().create(validated_data)
            purchases = Purchase.objects.filter(pk__in=purchases_ids)
            purchases.update(store_payment=store_payment)

            movement_data = {
                "movement_type": Movement.Type.ADMIN_BAR_PAYMENT,
                "store_payment": store_payment.id,
                "grouping_id": Movement.objects.get_next_grouping_id(),
            }
            movement_serializer = MovementSerializer(data=movement_data)
            movement_serializer.is_valid(raise_exception=True)
            movement_serializer.save()

            fund_account_origin = store_payment.funds_account_origin
            amount_to_extract = store_payment.amount
            if fund_account_origin.currency == FundAccount.Currency.VES:
                amount_to_extract *= store_payment.usd_exchange_rate

            fund_account_origin.balance -= amount_to_extract
            fund_account_origin.save()

        context = {
            "username": store_payment.store.user.username,
            "reference": store_payment.reference_number,
            "payment_date": store_payment.created_at,
            "total": store_payment.amount,
            "current_date": str(datetime.now(tz=timezone("America/Caracas")).date()),
            "usd_exchange_rate": store_payment.usd_exchange_rate,
            "total_local_currency": store_payment.amount * store_payment.usd_exchange_rate,
            "purchases": enumerate(purchases),
            "index_end": len(purchases) - 1,
        }
        message = (
            "You have received a payment from Beers totalling your current balance."
        )
        email_html_message = render_to_string("payments/payment_detail.html", context)
        email_plaintext_message = render_to_string(
            "payments/payment_detail.txt", context
        )
        email = EmailMultiAlternatives(
            subject="Beers payment received!",
            body=message,
            from_email=settings.EMAIL_HOST_USER,
            to=[store_payment.store.user.email],
        )
        content_type = guess_type(store_payment.receipt.name)[0]
        email.attach(
            store_payment.receipt.name, store_payment.receipt.read(), content_type
        )
        email.attach_alternative(email_html_message, "text/html")
        email.send()

        return store_payment


class MovementSerializer(serializers.ModelSerializer):
    purchase_info = serializers.SerializerMethodField()
    funding_info = serializers.SerializerMethodField()

    class Meta:
        model = Movement
        fields = [
            "id",
            "movement_type",
            "grouping_id",
            "purchase",
            "purchase_info",
            "funding",
            "funding_info",
            "admin_operation",
            "store_payment",
            "created_at",
        ]

    def get_purchase_info(self, obj):
        if obj.purchase is None:
            return

        purchase_serializer = PurchaseSerializer(obj.purchase)
        return purchase_serializer.data

    def get_funding_info(self, obj):
        if obj.funding is None:
            return

        funding_serializer = FundingSerializer(obj.funding)
        return funding_serializer.data

    def validate(self, attrs):
        purchase = attrs.get("purchase")
        funding = attrs.get("funding")

        if self.instance:
            # we're in an update
            return attrs

        movement_type = attrs.get("movement_type")
        movements_with_purchase = [
            Movement.Type.GIFT_RECEIVED.value,
            Movement.Type.GIFT_SENT.value,
            Movement.Type.GIFT_REJECTED.value,
            Movement.Type.GIFT_CLAIMED.value,
            Movement.Type.GIFT_REFUNDED.value,
            Movement.Type.BAR_CLAIM_PAYMENT.value,
        ]
        movements_with_funding = [
            Movement.Type.FUNDING.value,
            Movement.Type.ADMIN_FUNDING.value,
        ]
        if movement_type in movements_with_purchase and purchase is None:
            raise serializers.ValidationError(
                {
                    "type_&_purchase": f"Cannot create a Movement of type {movement_type} without a 'purchase'"
                }
            )
        elif movement_type == Movement.Type.FUNDING.value and funding is None:
            raise serializers.ValidationError(
                {
                    "type_&_funding": f"Cannot create a Movement of type {movement_type} without a 'funding'"
                }
            )

        return attrs


class ReadOnlyMovementSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()
    amount_local_currency = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    gift_info = serializers.SerializerMethodField()
    bar_claim_info = serializers.SerializerMethodField()
    operation_info = serializers.SerializerMethodField()
    commission_amount = serializers.SerializerMethodField()

    class Meta:
        model = Movement
        fields = [
            "id",
            "movement_type",
            "grouping_id",
            "username",
            "amount",
            "amount_local_currency",
            "purchase",
            "funding",
            "admin_operation",
            "store_payment",
            "gift_info",
            "bar_claim_info",
            "operation_info",
            "commission_amount",
            "created_at",
        ]
        depth = 1

    def get_amount(self, obj):
        if obj.purchase is not None:
            if obj.movement_type == Movement.Type.GIFT_REFUNDED:
                return obj.purchase.amount - (obj.purchase.amount * Decimal(0.15))
            elif obj.movement_type == Movement.Type.BAR_CLAIM_PAYMENT:
                return obj.purchase.amount - obj.purchase.commission_amount
            else:
                return obj.purchase.amount
        elif obj.funding is not None:
            return obj.funding.amount
        elif obj.admin_operation is not None:
            if obj.movement_type == Movement.Type.FUNDS_EXCHANGE_DESTINATION:
                return obj.admin_operation.amount_usd - obj.admin_operation.commission

            return obj.admin_operation.amount_usd
        elif obj.store_payment is not None:
            return obj.store_payment.amount

    def get_amount_local_currency(self, obj):
        if obj.movement_type == Movement.Type.FUNDING:
            return obj.funding.amount_local_currency

        return

    def get_username(self, obj):
        if obj.movement_type == Movement.Type.BAR_CLAIM_PAYMENT:
            return obj.purchase.store.name

        if obj.movement_type == Movement.Type.ADMIN_BAR_PAYMENT:
            return obj.store_payment.store.name

        if obj.purchase is not None:
            return obj.purchase.user.username
        elif obj.funding is not None:
            return obj.funding.user.username
        elif obj.admin_operation is not None:
            return obj.admin_operation.admin.username
        elif obj.store_payment is not None:
            return obj.store_payment.store.user.username

    def get_gift_info(self, obj):
        gift_movs = Movement.get_gift_types()
        if not obj.movement_type in gift_movs:
            return

        exchange_rate = usd_exchange_rate_service.get_usd_exchange_rate()
        gift_info = {
            "recipient_username": obj.purchase.gift_recipient.username,
            "amount_local_currency": self.get_amount(obj) * exchange_rate,
            "usd_exchange_rate": exchange_rate,
            "products": obj.purchase.products.filter(
                store_prices__store=obj.purchase.store,
                purchasehasproduct__purchase=obj.purchase,
            ).values("name", "purchasehasproduct__quantity", "store_prices__price"),
            "account": "Beers",
        }

        return gift_info

    def get_bar_claim_info(self, obj):
        if obj.movement_type != Movement.Type.BAR_CLAIM_PAYMENT:
            return

        return {"store_name": obj.purchase.store.name}

    def get_commission_amount(self, obj):
        gift_movs = Movement.get_gift_types()
        if obj.movement_type in gift_movs:
            if obj.movement_type == Movement.Type.GIFT_REFUNDED:
                return obj.purchase.amount * Decimal(0.15)
            elif obj.movement_type == Movement.Type.BAR_CLAIM_PAYMENT:
                return obj.purchase.amount * obj.purchase.commission_percentage

    def get_operation_info(self, obj):
        op_movs = Movement.get_operation_types()
        if not obj.movement_type in op_movs:
            return

        origin_acc_name = None
        if obj.admin_operation.origin_account is not None:
            origin_acc_name = obj.admin_operation.origin_account.name

        dest_acc_name = None
        if obj.admin_operation.destination_account is not None:
            dest_acc_name = obj.admin_operation.destination_account.name

        amount_local_currency = obj.admin_operation.amount_local_currency
        if obj.movement_type == Movement.Type.FUNDS_EXCHANGE_DESTINATION:
            amount_local_currency -= obj.admin_operation.commission

        usd_exchange_rate = (obj.admin_operation.usd_exchange_rate,)
        commission_rate = None
        exchange_movs = [
            Movement.Type.FUNDS_EXCHANGE_ORIGIN,
            Movement.Type.FUNDS_EXCHANGE_DESTINATION,
        ]
        if obj.movement_type in exchange_movs:
            if not obj.admin_operation.uses_usd_rate:
                usd_exchange_rate = None
                commission_rate = (
                    obj.admin_operation.amount - obj.admin_operation.commission
                ) / obj.admin_operation.amount

        return {
            "origin_acc_name": origin_acc_name,
            "dest_acc_name": dest_acc_name,
            "amount_local_currency": obj.admin_operation.amount_local_currency,
            "usd_exchange_rate": usd_exchange_rate,
            "commission_rate": commission_rate,
        }
