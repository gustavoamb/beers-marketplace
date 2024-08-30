from uuid import uuid4
from decimal import Decimal, ROUND_UP

from django.db import models
from django.core.validators import MinValueValidator

from common.models import TimeStampedModel

from common.utils import round_to_fixed_exponent


class FundAccount(TimeStampedModel):
    """Represents a company's funding account"""

    class Currency(models.TextChoices):
        USD = "USD", "(USD) United States dollar"
        VES = "VES", "(VES) Venezuelan sovereign bolívar"

    id = models.UUIDField(primary_key=True, default=uuid4)
    name = models.TextField()
    currency = models.CharField(max_length=3, choices=Currency.choices)
    balance = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="Amount of currency held in the account",
        default=0.00,
        validators=[MinValueValidator(0.00)],
    )


class FundOperation(TimeStampedModel):
    """Represents a money exchange operation involving one or two fund accounts"""

    id = models.UUIDField(primary_key=True, default=uuid4)
    admin = models.ForeignKey("users.User", on_delete=models.CASCADE)
    amount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="Amount of money involved",
    )
    origin_account = models.ForeignKey(
        FundAccount, on_delete=models.CASCADE, null=True, related_name="origin_account"
    )
    destination_account = models.ForeignKey(
        FundAccount,
        on_delete=models.CASCADE,
        null=True,
        related_name="destination_account",
    )
    usd_exchange_rate = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=1.0,
        help_text="USD exchange rate when the funding ocurred",
    )
    commission = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        default=0.0,
        help_text="USD exchange rate when the funding ocurred",
    )

    @property
    def has_origin(self):
        return self.origin_account is not None

    @property
    def has_destination(self):
        return self.destination_account is not None

    @property
    def is_exchange_op(self):
        return self.has_origin and self.has_destination

    @property
    def uses_usd_rate(self):
        return self.origin_account.currency != self.destination_account.currency

    @property
    def amount_local_currency(self):
        if self.is_exchange_op:
            if self.origin_account.currency == FundAccount.Currency.VES:
                return self.amount
        elif self.has_origin:
            # Withdrawal from origin account
            if self.origin_account.currency == FundAccount.Currency.VES:
                return self.amount
        elif self.has_destination:
            # Deposit into destination account
            if self.destination_account.currency == FundAccount.Currency.VES:
                return self.amount

        return round_to_fixed_exponent((self.amount * self.usd_exchange_rate))

    @property
    def amount_usd(self):
        if self.is_exchange_op:
            if self.origin_account.currency == FundAccount.Currency.USD:
                return self.amount
        elif self.has_origin:
            # Withdrawal from origin account
            if self.origin_account.currency == FundAccount.Currency.USD:
                return self.amount
        elif self.has_destination:
            # Deposit into destination account
            if self.destination_account.currency == FundAccount.Currency.USD:
                return self.amount

        return round_to_fixed_exponent((self.amount / self.usd_exchange_rate))
