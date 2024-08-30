from decimal import Decimal
from uuid import uuid4
from phonenumber_field.modelfields import PhoneNumberField

from django.db import models
from django.db.models import Sum, F

from common.models import TimeStampedModel

from payments.managers import MovementManager


# Create your models here.
class Funding(TimeStampedModel):
    class PaymentPlatform(models.TextChoices):
        STRIPE = "STRIPE", "Stripe"
        PAYPAL = "PAYPAL", "Paypal"
        MERCANTIL_PAGO_MOVIL = "MERCANTIL_PAGO_MOVIL", "Pago Movil - Mercantil"

    class Status(models.TextChoices):
        SUCCESSFUL = "SUCCESSFUL", "Successful"
        FAILED = "FAILED", "Failed"

    amount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="Base amount of money spent",
    )
    purchased_via = models.CharField(
        max_length=20, choices=PaymentPlatform.choices, default=PaymentPlatform.STRIPE
    )
    status = models.CharField(max_length=10, choices=Status.choices)
    reference = models.CharField(
        max_length=255,
        unique=True,
        help_text="Reference string used to identify the transaction in other platforms",
    )
    fee = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="The transaction's fee",
    )
    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    error = models.TextField(null=True)
    usd_exchange_rate = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        null=True,
        help_text="USD exchange rate when the funding ocurred",
    )

    @property
    def total_amount(self):
        return self.amount + self.fee

    @property
    def amount_local_currency(self):
        if not self.usd_exchange_rate:
            return

        return self.amount * self.usd_exchange_rate


class RechargeFundsSession(TimeStampedModel):
    class Status(models.TextChoices):
        IN_PROGRESS = ("IN_PROGRESS",)
        COMPLETED = ("COMPLETED",)

    user = models.ForeignKey("users.User", on_delete=models.CASCADE)
    status = models.CharField(
        max_length=11, choices=Status.choices, default=Status.IN_PROGRESS
    )
    payment_platform = models.CharField(
        max_length=20,
        choices=Funding.PaymentPlatform.choices,
        default=Funding.PaymentPlatform.STRIPE,
    )
    order = models.CharField(
        max_length=255,
        help_text=("String used to identify the transaction in other platforms, ")
        + (
            "the naming changes accordingly, for example these are called PaymentIntents in Stripe"
        ),
    )
    request_idempotency_key = models.UUIDField()


class StoreFundAccount(TimeStampedModel):
    """Account information where a Store receives it's beers payments"""

    class Type(models.TextChoices):
        VES = "VES", "local_currency"
        USD = "USD", "Dollars"
        MOBILE_PAY = "MOBILE_PAY", "Mobile payments (Pago Móvil)"
        PAYPAL = "PAYPAL", "Paypal"

    class DocType(models.TextChoices):
        RIF = "RIF", "Rif"
        CI = "CI", "Cedula"

    id = models.UUIDField(primary_key=True, default=uuid4)
    store = models.ForeignKey(
        "stores.Store", related_name="fund_accounts", on_delete=models.CASCADE
    )
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.USD)
    number = models.TextField(null=True)
    holder_name = models.TextField(null=True)
    bank_name = models.TextField(null=True)
    doc_type = models.CharField(max_length=14, choices=DocType.choices, null=True)
    doc_number = models.TextField(null=True)
    phone = PhoneNumberField(null=True)
    is_preferential = models.BooleanField(default=False)


class StorePayment(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid4)
    store = models.ForeignKey(
        "stores.Store", related_name="payments", on_delete=models.CASCADE
    )
    amount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="Amount paid to the Store",
    )
    reference = models.IntegerField(
        unique=True,
        help_text="Payment reference to be displayed to end users",
        null=True,
    )
    receipt = models.FileField(upload_to="stores")
    funds_account_origin = models.ForeignKey(
        "administration.FundAccount", on_delete=models.CASCADE, null=True
    )
    usd_exchange_rate = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="USD exchange rate when the payment ocurred",
    )

    @property
    def amount_local_currency(self):
        return self.amount * self.usd_exchange_rate

    @property
    def commission_amount_local_currency(self):
        commissions = self.purchases.annotate(
            commission_amount=F("amount") * F("commission_percentage")
        ).aggregate(total=Sum("commission_amount"))["total"]
        if not commissions:
            commissions = Decimal(0)

        return commissions * self.usd_exchange_rate

    def save(self, *args, **kwargs):
        if self._state.adding:
            last_payment = StorePayment.objects.order_by("created_at").last()
            if last_payment is None:
                self.reference = 1
            else:
                self.reference = last_payment.reference + 1

        return super(StorePayment, self).save(*args, **kwargs)

    @property
    def reference_number(self):
        return str(self.reference).zfill(6)


class Movement(TimeStampedModel):
    class Type(models.TextChoices):
        GIFT_RECEIVED = "GIFT_RECEIVED", "Gift received"
        GIFT_SENT = "GIFT_SENT", "Gift sent"
        GIFT_ACCEPTED = "GIFT_ACCEPTED", "Gift accepted"
        GIFT_REJECTED = "GIFT_REJECTED", "Gift rejected"
        GIFT_REFUNDED = "GIFT_REFUNDED", "Gift refunded"
        GIFT_EXPIRED = "GIFT_EXPIRED", "Gift expired"
        GIFT_CLAIMED = "GIFT_CLAIMED", "Gift claimed"
        BAR_CLAIM_PAYMENT = "BAR_CLAIM_PAYMENT", "Payment to a bar due to gift claim"
        FUNDING = "FUNDING", "Funding performed"
        ADMIN_FUNDING = "ADMIN_FUNDING", "Funding performed by an admin"
        ADMIN_BAR_PAYMENT = "ADMIN_BAR_PAYMENT", "Payment to a bar by an admin"
        ADMIN_FUNDS_WITHDRAWAL = (
            "ADMIN_FUNDS_WITHDRAWAL",
            "Funds withdrawed by an admin",
        )
        FUNDS_EXCHANGE_ORIGIN = "FUNDS_EXCHANGE_ORIGIN", "Currency exchange to "
        FUNDS_EXCHANGE_DESTINATION = (
            "FUNDS_EXCHANGE_DESTINATION",
            "Currency exchange to ",
        )

    movement_type = models.CharField(max_length=26, choices=Type.choices)
    grouping_id = models.IntegerField(
        help_text="Used to group two or more related movements together",
    )
    purchase = models.ForeignKey("stores.Purchase", on_delete=models.CASCADE, null=True)
    funding = models.ForeignKey(Funding, on_delete=models.CASCADE, null=True)
    admin_operation = models.ForeignKey(
        "administration.FundOperation", on_delete=models.CASCADE, null=True
    )
    store_payment = models.ForeignKey(StorePayment, on_delete=models.CASCADE, null=True)

    objects = MovementManager()

    @staticmethod
    def get_gift_types():
        return [
            Movement.Type.GIFT_SENT,
            Movement.Type.GIFT_RECEIVED,
            Movement.Type.GIFT_REJECTED,
            Movement.Type.GIFT_REFUNDED,
            Movement.Type.GIFT_EXPIRED,
            Movement.Type.GIFT_CLAIMED,
            Movement.Type.BAR_CLAIM_PAYMENT,
        ]

    @staticmethod
    def get_operation_types():
        return [
            Movement.Type.ADMIN_FUNDING,
            Movement.Type.ADMIN_FUNDS_WITHDRAWAL,
            Movement.Type.FUNDS_EXCHANGE_ORIGIN,
            Movement.Type.FUNDS_EXCHANGE_DESTINATION,
        ]
