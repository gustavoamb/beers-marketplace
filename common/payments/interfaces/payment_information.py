class PaymentInformation:
    def __init__(self, amount, external_customer_id=None, idempotency_key=None):
        self.amount = amount
        self.currency = "usd"
        self.customer = external_customer_id
        self.idempotency_key = idempotency_key


class TransactionCapture:
    def __init__(self, external_transaction_id):
        self.id = external_transaction_id


class WebhookEvent:
    pass
