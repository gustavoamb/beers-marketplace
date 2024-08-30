from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch

from rest_framework import serializers

from administration.models import FundAccount, FundOperation

from stores.models import Product, Store, Purchase, PurchaseHasProduct

from payments.models import Movement, StorePayment
from payments.serializers import (
    MovementSerializer,
    StorePaymentSerializer,
    StoreFundAccountSerializer,
)

from users.models import SystemCurrency

from common.money_exchange.dolar_venezuela import usd_exchange_rate_service
from common.utils import round_to_fixed_exponent


class FundAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = FundAccount
        fields = ["id", "name", "currency", "balance"]


class FundOperationSerializerHelper:
    def __init__(self, operation: FundOperation):
        self.operation = operation
        has_origin_acc = self.operation.origin_account is not None
        has_dest_acc = self.operation.destination_account is not None
        self.is_exchange_op = has_origin_acc and has_dest_acc

    def __create_exchange_movements(self):
        exchange_types = [
            Movement.Type.FUNDS_EXCHANGE_ORIGIN.value,
            Movement.Type.FUNDS_EXCHANGE_DESTINATION.value,
        ]
        grouping_id = Movement.objects.get_next_grouping_id()
        movements_data = [
            {
                "movement_type": mov_type,
                "admin_operation": self.operation.id,
                "grouping_id": grouping_id,
            }
            for mov_type in exchange_types
        ]
        movement_serializer = MovementSerializer(data=movements_data, many=True)
        movement_serializer.is_valid(raise_exception=True)
        movement_serializer.save()

    def create_related_movements(self):
        if self.is_exchange_op:
            return self.__create_exchange_movements()

        deposit_type = Movement.Type.ADMIN_FUNDING.value
        withdrawal_type = Movement.Type.ADMIN_FUNDS_WITHDRAWAL.value
        is_deposit = self.operation.amount > 0
        movement_type = deposit_type if is_deposit else withdrawal_type
        movement_data = {
            "movement_type": movement_type,
            "admin_operation": self.operation.id,
            "grouping_id": Movement.objects.get_next_grouping_id(),
        }
        movement_serializer = MovementSerializer(data=movement_data)
        movement_serializer.is_valid(raise_exception=True)
        movement_serializer.save()

    def modify_accounts_balances(self):
        if self.is_exchange_op:
            origin_acc = self.operation.origin_account
            dest_acc = self.operation.destination_account
            dest_amount = self.operation.amount
            if origin_acc.currency != dest_acc.currency:
                if origin_acc.currency == FundAccount.Currency.USD.value:
                    dest_amount *= self.operation.usd_exchange_rate
                elif origin_acc.currency == FundAccount.Currency.VES.value:
                    dest_amount /= self.operation.usd_exchange_rate

            dest_amount -= Decimal(self.operation.commission)

            origin_acc.balance -= self.operation.amount
            origin_acc.save()
            dest_acc.balance += dest_amount
            dest_acc.save()
            return

        account = self.operation.destination_account
        is_funds_withdrawal = self.operation.amount < 0
        if is_funds_withdrawal:
            account = self.operation.origin_account

        account.balance += self.operation.amount
        account.save()


class FundOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FundOperation
        fields = [
            "id",
            "admin",
            "amount",
            "origin_account",
            "destination_account",
            "usd_exchange_rate",
            "commission",
        ]
        read_only_fields = ["admin"]

    def validate_amount(self, amount):
        if amount == 0:
            raise serializers.ValidationError("Cannot be 0")

        return amount

    def validate(self, data):
        amount = data.get("amount")
        origin = data.get("origin_account", None)
        destination = data.get("destination_account", None)
        if origin == destination:
            raise serializers.ValidationError(
                {
                    "origin_account_&_destination_account": "origin and destination accounts cannot be the same"
                }
            )

        has_origin_and_dest = origin is not None and destination is not None
        if has_origin_and_dest and origin.currency == destination.currency:
            data["usd_exchange_rate"] = 1.0

        is_funds_withdrawal = amount < 0
        if is_funds_withdrawal:
            if origin is None:
                raise serializers.ValidationError(
                    {
                        "amount_&_origin_account": "'origin_account' field is required when 'amount' is negative"
                    }
                )
            if destination is not None:
                raise serializers.ValidationError(
                    {
                        "amount_&_origin_account_&_destination_account": "'amount' cannot be negative when alongside 'origin_account' and 'destination_account'"
                    }
                )
        else:
            if destination is None:
                raise serializers.ValidationError(
                    {
                        "amount_&_destination_account": "'destination_account' field is required when 'amount' is positive"
                    }
                )

        if origin is not None and origin.balance < abs(amount):
            raise serializers.ValidationError(
                {
                    "amount_&_origin_account": "Insufficient balance in origin fund account to perform operation."
                }
            )

        return data

    def create(self, validated_data):
        fund_operation = super().create(validated_data)

        with transaction.atomic():
            helper = FundOperationSerializerHelper(fund_operation)
            helper.create_related_movements()
            helper.modify_accounts_balances()

            return fund_operation


class AdminStoreSerializer(serializers.ModelSerializer):
    user_email = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            "id",
            "created_at",
            "name",
            "doc_type",
            "doc_number",
            "contact_name",
            "contact_job",
            "contact_phone",
            "phone",
            "user_email",
            "verified",
            "commission_percentage",
        ]
        read_only_fields = ["user_email"]

    def get_user_email(self, obj):
        return obj.user.email


class AdminStoreBalanceSerializer(serializers.ModelSerializer):
    last_payment_date = serializers.SerializerMethodField()
    preferential_account = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    balance_local_currency = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "contact_name",
            "phone",
            "last_payment_date",
            "preferential_account",
            "balance",
            "balance_local_currency",
        ]

    def get_last_payment_date(self, obj):
        if not obj.last_payment_date:
            return

        return obj.last_payment_date

    def get_preferential_account(self, obj):
        if len(obj.preferential_account) == 0:
            return

        serializer = StoreFundAccountSerializer(
            obj.preferential_account[0],
            fields=["bank_name", "number", "doc_type", "doc_number"],
        )
        return serializer.data

    def get_balance(self, obj):
        return obj.balance

    def get_balance_local_currency(self, obj):
        usd_exchange = self.context["usd_ves_rate"]
        return round_to_fixed_exponent(obj.balance * Decimal(usd_exchange))


class AdminStorePaymentSerializer(StorePaymentSerializer):
    class Meta:
        model = StorePayment
        fields = [
            "id",
            "store",
            "amount",
            "amount_local_currency",
            "commission_amount_local_currency",
            "reference_number",
            "receipt",
            "funds_account_origin",
            "usd_exchange_rate",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["amount_local_currency", "reference_number"]


class AdminPurchaseProductSerializer(serializers.ModelSerializer):
    quantity = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "quantity"]
        read_only_fields = ["id", "name", "quantity"]

    def get_quantity(self, obj):
        return obj.detail[0].quantity


class UnclaimedPurchaseSerialiser(serializers.ModelSerializer):
    products = serializers.SerializerMethodField()

    class Meta:
        model = Purchase
        fields = [
            "id",
            "status",
            "amount",
            "commission_amount",
            "gift_has_expired",
            "qr_scanned",
            "store",
            "products",
        ]

    def get_products(self, obj):
        purchase_has_product = PurchaseHasProduct.objects.filter(purchase=obj.id)
        products = obj.products.prefetch_related(
            Prefetch(
                "purchasehasproduct_set",
                queryset=purchase_has_product,
                to_attr="detail",
            ),
        )
        serializer = AdminPurchaseProductSerializer(products, many=True)
        return serializer.data


class SystemCurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemCurrency
        fields = ["id", "name", "iso_code", "ves_exchange_rate"]
