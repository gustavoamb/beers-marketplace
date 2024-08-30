import os
from decimal import Decimal, ROUND_UP

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from payments.models import Funding
from payments.serializers import FundingSerializer
from stores.serializers import PurchaseSerializer, PurchaseHasProductSerializer
from users.serializers import UserSerializer
from administration.models import FundAccount
from administration.serializers import FundAccountSerializer

from stores.models import Product
from users.models import User

from common.money_exchange.dolar_venezuela import usd_exchange_rate_service

ADD_FUNDS_PRODUCT_ID = os.getenv("STRIPE_ADD_FUNDS_PRODUCT_ID")


def add_funds_to_customer(customer_id, funds_quantity):
    customer = User.objects.get(pk=customer_id)
    current_balance = customer.balance
    new_balance = current_balance + Decimal(str(funds_quantity)).quantize(
        Decimal("0.01"), rounding=ROUND_UP
    )
    customer_serializer = UserSerializer(
        customer, data={"balance": new_balance}, partial=True
    )
    customer_serializer.is_valid(raise_exception=True)
    customer_serializer.save()


def add_funds_to_admin_account(funds_quantity, account):
    current_balance = account.balance
    new_balance = current_balance + Decimal(str(funds_quantity)).quantize(
        Decimal("0.01"), rounding=ROUND_UP
    )
    admin_account_serializer = FundAccountSerializer(
        account, data={"balance": new_balance}, partial=True
    )
    admin_account_serializer.is_valid(raise_exception=True)
    admin_account_serializer.save()


def send_receipt_email(customer, funding):
    context = {
        "username": customer.username,
        "purchased_via": funding.purchased_via,
        "amount": funding.amount,
        "created_at": funding.created_at,
        "fee": funding.fee,
        "total": funding.total_amount,
    }
    email_html_message = render_to_string("payments/receipt.html", context)
    email_plaintext_message = render_to_string("payments/receipt.txt", context)
    email = EmailMultiAlternatives(
        subject="beers payment received!",
        body=email_plaintext_message,
        from_email=settings.EMAIL_HOST_USER,
        to=[customer.email],
    )
    email.attach_alternative(email_html_message, "text/html")
    email.send(fail_silently=True)


class StripeOrderHandler:
    def __init__(self, stripe_client, payment_intent):
        self.__client = stripe_client
        self.payment_status = payment_intent.status
        self.customer_stripe_id = payment_intent.customer
        self.payment_intent_id = payment_intent.id
        self.amount = payment_intent.amount / 100

    def __handle_funding(self):
        customer = User.objects.get(stripe_id=self.customer_stripe_id)
        serializer_data = {
            "user": customer.id,
            "amount": self.amount,
            "purchased_via": Funding.PaymentPlatform.STRIPE,
            "status": Funding.Status.SUCCESSFUL,
            "reference": self.payment_intent_id,
            "fee": self.__client.get_payment_fee(self.amount),
        }
        funding_serializer = FundingSerializer(data=serializer_data)
        funding_serializer.is_valid(raise_exception=True)
        funding = funding_serializer.save()
        add_funds_to_customer(customer.id, self.amount)

        admin_stripe_acc = FundAccount.objects.get(name__iexact="stripe")
        add_funds_to_admin_account(self.amount, admin_stripe_acc)
        send_receipt_email(customer, funding)

    def handle_payment_failure(self, err_msg):
        customer = User.objects.get(stripe_id=self.customer_stripe_id)
        serializer_data = {
            "user": customer.id,
            "amount": self.amount,
            "purchased_via": Funding.PaymentPlatform.STRIPE,
            "status": Funding.Status.FAILED,
            "reference": self.payment_intent_id,
            "fee": self.__client.get_payment_fee(self.amount),
            "error": err_msg,
        }
        funding_serializer = FundingSerializer(data=serializer_data)
        funding_serializer.is_valid(raise_exception=True)
        funding_serializer.save()

    def fulfill_order(self):
        if self.payment_status == "requires_payment_method":
            self.handle_payment_failure()

        if not (self.payment_status == "succeeded"):
            return

        self.__handle_funding()


class PaypalOrderHandler:
    def __init__(self, capture_data):
        self.reference_id = capture_data["id"]
        self.payment_status = capture_data["status"]
        self.purchase_units = capture_data["purchase_units"]
        if "payments" in capture_data["purchase_units"][0].keys():
            self.customer_id = capture_data["purchase_units"][0]["payments"][
                "captures"
            ][0]["custom_id"]
        else:
            self.customer_id = capture_data["purchase_units"][0]["custom_id"]

    def __get_purchase_units_total_amount(self):
        total = sum([float(unit["amount"]["value"]) for unit in self.purchase_units])
        return total

    def __handle_funding(self, captures):
        total_amount = 0
        total_fee = 0
        for capture in captures:
            if capture["status"] == "COMPLETED":
                total_amount += float(capture["amount"]["value"])

        serializer_data = {
            "user": self.customer_id,
            "amount": total_amount,
            "purchased_via": Funding.PaymentPlatform.PAYPAL,
            "status": Funding.Status.SUCCESSFUL,
            "reference": self.reference_id,
            "fee": total_fee,
        }
        funding_serializer = FundingSerializer(data=serializer_data)
        funding_serializer.is_valid(raise_exception=True)
        funding = funding_serializer.save()
        add_funds_to_customer(self.customer_id, total_amount)

        admin_paypal_acc = FundAccount.objects.get(name__iexact="paypal")
        add_funds_to_admin_account(total_amount, admin_paypal_acc)
        customer = User.objects.get(id=self.customer_id)
        send_receipt_email(customer, funding)
        return funding_serializer.data

    def handle_payment_failure(self, order_error):
        serializer_data = {
            "user": self.customer_id,
            "amount": self.__get_purchase_units_total_amount(),
            "purchased_via": Funding.PaymentPlatform.PAYPAL,
            "status": Funding.Status.FAILED,
            "reference": self.reference_id,
            "fee": 0,
            "error": order_error.get_error_msg(),
        }
        funding_serializer = FundingSerializer(data=serializer_data)
        funding_serializer.is_valid(raise_exception=True)
        funding_serializer.save()
        return funding_serializer.data

    def handle_order_item(self, item):
        captures = item["payments"]["captures"]

        return self.__handle_funding(captures)

    def fulfill_order(self):
        if not (self.payment_status == "COMPLETED"):
            return

        purchases = [self.handle_order_item(item) for item in self.purchase_units]
        return purchases


class MercantilOrderHandler:
    def __init__(self, mobile_payment, customer_id):
        self._amount = mobile_payment.get("amount")
        self._payment_reference = mobile_payment.get("payment_reference")
        self._customer_id = customer_id

    def __get_dollar_amount(self):
        dollar_exchange = usd_exchange_rate_service.get_usd_exchange_rate()
        dollar_amount = round(Decimal(str(self._amount)) / dollar_exchange, 2)
        return dollar_amount, dollar_exchange

    def handle_payment_failure(self, err_msgs):
        dollar_amount, usd_exchange_rate = self.__get_dollar_amount()
        serializer_data = {
            "user": self._customer_id,
            "amount": dollar_amount,
            "purchased_via": Funding.PaymentPlatform.MERCANTIL_PAGO_MOVIL,
            "status": Funding.Status.FAILED,
            "reference": self._payment_reference,
            "fee": 0,
            "error": "".join(err_msgs),
            "usd_exchange_rate": usd_exchange_rate,
        }
        funding_serializer = FundingSerializer(data=serializer_data)
        funding_serializer.is_valid(raise_exception=True)
        funding_serializer.save()
        return funding_serializer.data

    def handle_funding(self):
        (
            dollar_amount,
            usd_exchange_rate,
        ) = self.__get_dollar_amount()
        serializer_data = {
            "user": self._customer_id,
            "amount": dollar_amount,
            "purchased_via": Funding.PaymentPlatform.MERCANTIL_PAGO_MOVIL,
            "status": Funding.Status.SUCCESSFUL,
            "reference": self._payment_reference,
            "fee": 0,
            "usd_exchange_rate": usd_exchange_rate,
        }
        funding_serializer = FundingSerializer(data=serializer_data)
        funding_serializer.is_valid(raise_exception=True)
        funding = funding_serializer.save()
        add_funds_to_customer(self._customer_id, dollar_amount)
        customer = User.objects.get(id=self._customer_id)
        send_receipt_email(customer, funding)

        admin_mercantil_acc = FundAccount.objects.get(name__iexact="mercantil")
        add_funds_to_admin_account(self._amount, admin_mercantil_acc)
        return funding_serializer.data
