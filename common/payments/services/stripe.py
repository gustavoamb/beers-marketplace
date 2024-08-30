import os
from enum import Enum
from decimal import Decimal, ROUND_DOWN

from common.payments.interfaces.payments import PaymentServiceInterface
from common.payments.config import stripe
from common.payments.interfaces.customer import Customer
from common.payments.interfaces.payment_information import (
    PaymentInformation,
    TransactionCapture,
    WebhookEvent,
)


class EventTypes(Enum):
    # There's quite alot more than these, but since the SDK doesn't have them available,
    # we're just listing the one's we're interested in
    PAYMENT_INTENT_PROCESSING = "payment_intent.processing"
    PAYMENT_INTENT_SUCCEEDED = "payment_intent.succeeded"
    PAYMENT_INTENT_PAYMENT_FAILED = "payment_intent.payment_failed"
    CHECKOUT_SESSION_COMPLETED = "checkout.session.completed"


class StripeSetupIntents:
    def __init__(self):
        self._client = stripe

    def create_setup_intent(self, customer_id):
        setup_intent = self._client.SetupIntent.create(
            customer=customer_id,
            payment_method_types=["card"],
        )

        return setup_intent

    def confirm_setup_intent(self, setup_intent_id):
        setup_intent = self._client.SetupIntent.confirm(setup_intent_id)

        return setup_intent

    def list_customer_setup_intents(self, customer_id):
        setup_intents = self._client.SetupIntent.list(customer=customer_id)
        return setup_intents


class StripePaymentMethods:
    def __init__(self):
        self._client = stripe

    def retrieve_customer_payment_method(self, customer_id, payment_method_id):
        payment_method = self._client.Customer.retrieve_payment_method(
            customer_id, payment_method_id
        )

        return payment_method

    def list_customer_payment_methods(self, customer_id):
        payment_methods = self._client.PaymentMethod.list(
            customer=customer_id,
            type="card",
        )

        return payment_methods

    def update_payment_method(self, payment_method_id, payload):
        payment_method_updated = self._client.PaymentMethod.modify(
            payment_method_id,
            **payload,
        )

        return payment_method_updated

    def detach_payment_method(self, payment_method_id):
        self._client.PaymentMethod.detach(
            payment_method_id,
        )


class StripeCharges:
    def __init__(self):
        self._client = stripe

    def search_charges(self, query):
        charges = self._client.Charge.search(query=query, limit=1)
        return charges


class StripeCheckout:
    def __init__(self):
        self._client = stripe

    def create_checkout_session(self, payload):
        customer = payload.get("customer")
        product_price_id = payload.get("product_price_id")
        product_quantity = payload.get("product_quantity")
        domain = payload.get("domain")

        checkout_session = self._client.checkout.Session.create(
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    "price": product_price_id,
                    "quantity": product_quantity,
                },
            ],
            mode="payment",
            success_url=f"http://{domain}" + "/success.html",
            cancel_url=f"http://{domain}" + "/cancel.html",
            customer=customer,
        )

        return checkout_session

    def handle_checkout_completed_event(self, event):
        if event["type"] == EventTypes.CHECKOUT_SESSION_COMPLETED.value:
            # Retrieve the session. If you require line items in the response,
            # you may include them by expanding line_items.
            session = self._client.checkout.Session.retrieve(
                event["data"]["object"]["id"],
                expand=["line_items", "payment_intent"],
            )

            return session


class StripeWebhook:
    def __init__(self):
        self._client = stripe

    def construct_event_from_webhook_request(self, request):
        payload = request.body.decode("utf-8")  # We need the raw body for this one.
        sig_header = request.META["HTTP_STRIPE_SIGNATURE"]
        endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

        event = self._client.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )

        return event

    def handle_paymentintent_event(self, event):
        event_type = event["type"]
        if event_type != EventTypes.PAYMENT_INTENT_SUCCEEDED.value:
            return

        payment_intent = self._client.PaymentIntent.retrieve(
            event["data"]["object"]["id"]
        )
        return payment_intent


class StripeService(
    PaymentServiceInterface,
    StripeSetupIntents,
    StripePaymentMethods,
    StripeCharges,
    StripeCheckout,
    StripeWebhook,
):
    def __init__(self):
        self._client = stripe

    def create_customer(self, customer: Customer):
        stripe_customer = self._client.Customer.create(**customer)

        customer = Customer()
        customer.save_stripe_customer(stripe_customer)

        return customer

    def create_payment_legacy(self, payment_information):
        checkout_session = self.create_checkout_session(payment_information)
        return checkout_session

    def create_payment(self, payment_information: PaymentInformation):
        # Why are we multiplying by 100? From the Stripe drocs:
        # All API requests expect amounts to be provided in a currency’s smallest unit.
        # For example, to charge 10 USD, provide an amount value of 1000 (that is, 1000 cents).
        amount = payment_information.amount * 100
        currency = payment_information.currency  # We only accept USD in this flow.
        customer = payment_information.customer
        idempotency_key = payment_information.idempotency_key
        payment_intent = self._client.PaymentIntent.create(
            amount=amount,
            currency=currency,
            customer=customer,
            setup_future_usage="on_session",
            idempotency_key=idempotency_key,
        )

        return payment_intent

    def get_payment(self, payment_intent_id):
        payment_intent = self._client.PaymentIntent.retrieve(payment_intent_id)
        return payment_intent

    def update_payment(self, sid, payment_information: PaymentInformation):
        amount = payment_information.amount * 100
        customer = payment_information.customer
        payment_intent = self._client.PaymentIntent.modify(
            sid,
            amount=amount,
            customer=customer,
        )

        return payment_intent

    def confirm_payment(self, payment_intent_id, payment_method_id):
        payment_intent = self._client.PaymentIntent.confirm(
            payment_intent_id, payment_method=payment_method_id
        )
        return payment_intent

    def capture_payment_legacy(self, payload: WebhookEvent):
        event = self.construct_event_from_webhook_request(payload)
        checkout_session = self.handle_checkout_completed_event(event)
        return checkout_session

    def capture_payment(self, event: TransactionCapture):
        handled_event = self.construct_event_from_webhook_request(event)
        payment_intent = self.handle_paymentintent_event(handled_event)
        return payment_intent

    def get_payment_fee(self, amount):
        fixed_fee = float(os.getenv("STRIPE_CARD_FIXED_FEE", 0.30))  # 30 cents
        percentage_fee = float(os.getenv("STRIPE_CARD_PERCENTAGE_FEE", 0.029))  # 2.9%
        amount_with_fee = (amount + fixed_fee) / (1 - percentage_fee)
        return Decimal(amount_with_fee - amount).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )


stripe_service = StripeService()
