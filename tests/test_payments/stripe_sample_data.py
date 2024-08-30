import os

payment_intent_creation_sample_data = {
    "id": "pi_1DsvUu2eZvKYlo2Cr73majm2",
    "object": "payment_intent",
    "amount": 2000,
    "amount_capturable": 0,
    "amount_details": {"tip": {}},
    "amount_received": 0,
    "application": None,
    "application_fee_amount": None,
    "automatic_payment_methods": {"enabled": True},
    "canceled_at": None,
    "cancellation_reason": None,
    "capture_method": "automatic",
    "client_secret": "pi_1DsvUu2eZvKYlo2Cr73majm2_secret_JvvzFcs9XKQWkwFiL53RNUV17",
    "confirmation_method": "automatic",
    "created": 1547572484,
    "currency": "usd",
    "customer": "user_stripe_id",
    "description": "Yellow fish #78925",
    "invoice": None,
    "last_payment_error": None,
    "latest_charge": None,
    "livemode": False,
    "metadata": {},
    "next_action": None,
    "on_behalf_of": None,
    "payment_method": None,
    "payment_method_options": {},
    "payment_method_types": ["card"],
    "processing": None,
    "receipt_email": None,
    "review": None,
    "setup_future_usage": None,
    "shipping": None,
    "statement_descriptor": None,
    "statement_descriptor_suffix": None,
    "status": "succeeded",
    "transfer_data": None,
    "transfer_group": None,
}

webhook_event_sample = {
    "id": "evt_3MMyjVIyqR9ZFNZ02DYZjVnk",
    "object": "event",
    "api_version": "2022-11-15",
    "created": 1672945449,
    "data": {
        "object": {
            "id": "pi_3MMyjVIyqR9ZFNZ023Fwskvm",
            "object": "payment_intent",
            "amount": 5.00,
            "amount_capturable": 0,
            "amount_details": {"tip": {}},
            "amount_received": 0,
            "application": None,
            "application_fee_amount": None,
            "automatic_payment_methods": None,
            "canceled_at": None,
            "cancellation_reason": None,
            "capture_method": "automatic",
            "client_secret": "pi_3MMyjVIyqR9ZFNZ023Fwskvm_secret_86k4dzmavsUJTPsBopftZk7Uk",
            "confirmation_method": "automatic",
            "created": 1672945449,
            "currency": "usd",
            "customer": None,
            "description": None,
            "invoice": None,
            "last_payment_error": None,
            "latest_charge": None,
            "livemode": False,
            "metadata": {},
            "next_action": None,
            "on_behalf_of": None,
            "payment_method": None,
            "payment_method_options": {
                "card": {
                    "installments": None,
                    "mandate_options": None,
                    "network": None,
                    "request_three_d_secure": "automatic",
                }
            },
            "payment_method_types": ["card"],
            "processing": None,
            "receipt_email": None,
            "review": None,
            "setup_future_usage": None,
            "shipping": None,
            "source": None,
            "statement_descriptor": None,
            "statement_descriptor_suffix": None,
            "status": "requires_payment_method",
            "transfer_data": None,
            "transfer_group": None,
        }
    },
    "livemode": False,
    "pending_webhooks": 2,
    "request": {
        "id": "req_PVREgBMLc15PhO",
        "idempotency_key": "4cc5c58c-413d-4b03-b2ec-5606eb359a0a",
    },
    "type": "payment_intent.created",
}

checkout_session_sample_data = {
    "id": "cs_test_a1LTgVr5E3PL8kszgzL7iZEXkPo0WN5Rr0UZ0xaSAIgE4qDCFrnw0CZt49",
    "object": "checkout.session",
    "after_expiration": None,
    "allow_promotion_codes": None,
    "amount_subtotal": 500,
    "amount_total": 500,
    "automatic_tax": {"enabled": False, "status": None},
    "billing_address_collection": None,
    "cancel_url": "http://localhost:8000/cancel.html",
    "client_reference_id": None,
    "consent": None,
    "consent_collection": None,
    "created": 1674056574,
    "currency": "usd",
    "custom_text": {"shipping_address": None, "submit": None},
    "customer": "user_stripe_id",
    "customer_creation": None,
    "customer_details": {
        "address": {
            "city": None,
            "country": "VE",
            "line1": None,
            "line2": None,
            "postal_code": None,
            "state": None,
        },
        "email": "daniel.varela@novateva.com",
        "name": "Daniel Varela",
        "phone": None,
        "tax_exempt": "none",
        "tax_ids": [],
    },
    "customer_email": None,
    "expires_at": 1674142974,
    "invoice": None,
    "invoice_creation": {
        "enabled": False,
        "invoice_data": {
            "account_tax_ids": None,
            "custom_fields": None,
            "description": None,
            "footer": None,
            "metadata": {},
            "rendering_options": None,
        },
    },
    "livemode": False,
    "locale": None,
    "metadata": {},
    "mode": "payment",
    "payment_intent": "pi_3MRdnAIyqR9ZFNZ02CigI7HG",
    "payment_link": None,
    "payment_method_collection": "always",
    "payment_method_options": {},
    "payment_method_types": ["card"],
    "payment_status": "paid",
    "phone_number_collection": {"enabled": False},
    "recovered_from": None,
    "setup_intent": None,
    "shipping_address_collection": None,
    "shipping_cost": None,
    "shipping_details": None,
    "shipping_options": [],
    "status": "complete",
    "submit_type": None,
    "subscription": None,
    "success_url": "http://localhost:8000/success.html",
    "total_details": {"amount_discount": 0, "amount_shipping": 0, "amount_tax": 0},
    "url": None,
    "line_items": [
        {
            "amount_subtotal": 500,
            "amount_tax": 0,
            "quantity": 500,
            "price": {"product": os.getenv("STRIPE_ADD_FUNDS_PRODUCT_ID")},
        }
    ],
}

outcome_sample_data = {
    "network_status": "not_sent_to_network",
    "reason": "highest_risk_level",
    "risk_level": "highest",
    "seller_message": "Stripe blocked this charge as too risky.",
    "type": "blocked",
}

charge_sample_data = {"outcome": outcome_sample_data}


class LineItemPrice:
    def __init__(self, price):
        self.product = price["product"]


class LineItem:
    def __init__(self, line_item):
        self.amount_subtotal = line_item["amount_subtotal"]
        self.amount_tax = line_item["amount_tax"]
        self.quantity = line_item["quantity"]
        self.price = LineItemPrice(line_item["price"])


class CheckoutSession:
    def __init__(self, checkout_session_data):
        self.payment_status = checkout_session_data["payment_status"]
        self.customer = checkout_session_data["customer"]
        self.payment_intent = checkout_session_data["payment_intent"]
        self.line_items = [
            LineItem(item) for item in checkout_session_data["line_items"]
        ]


class PaymentIntent:
    def __init__(self, payment_intent_data):
        self.id = payment_intent_data["id"]
        self.status = payment_intent_data["status"]
        self.customer = payment_intent_data["customer"]
        self.amount = payment_intent_data["amount"]


class Outcome:
    def __init__(self, outcome_data):
        self.seller_message = outcome_data["seller_message"]


class Charge:
    def __init__(self, charge_data):
        self.outcome = Outcome(charge_data["outcome"])


checkout_session_sample = CheckoutSession(checkout_session_sample_data)
payment_intent_sample = PaymentIntent(payment_intent_creation_sample_data)
charge_sample = Charge(charge_sample_data)
