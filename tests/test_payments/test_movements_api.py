import pytest

from datetime import datetime, timezone
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile

from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from payments.models import Funding, Movement
from payments.serializers import (
    FundingSerializer,
)
from payments.views import MovementsView

from stores.models import Purchase
from stores.serializers import PurchaseSerializer

from administration.serializers import (
    FundOperationSerializer,
    AdminStorePaymentSerializer,
)

request_factory = APIRequestFactory()
client = APIClient()


@pytest.fixture
def fundings(user):
    data = [
        Funding(user=user, amount=20.00, reference="stripe_payment_intent_1", fee=0.00),
        Funding(user=user, amount=7.25, reference="stripe_payment_intent_2", fee=0.00),
    ]
    fundings = Funding.objects.bulk_create(data)
    return fundings


@pytest.fixture
def movements(fundings):
    data = [
        Movement(
            funding=funding, movement_type=Movement.Type.FUNDING, grouping_id=index
        )
        for index, funding in enumerate(fundings)
    ]
    movements = Movement.objects.bulk_create(data)
    return movements


@pytest.mark.django_db
@patch("payments.serializers.FundingSerializer.get_payment_method")
def test_get_user_movements(funding_get_payment_mock, user, movements):
    funding_get_payment_mock.return_vale = "**** **** **** 4242"
    request = request_factory.get("beers/movements/")
    force_authenticate(request, user)
    view = MovementsView.as_view({"get": "list"})
    response = view(request)
    data = response.data

    expected_movements_count = len(movements)

    assert response.status_code == status.HTTP_200_OK
    assert data["count"] == expected_movements_count


@pytest.mark.django_db
def test_GIFT_SENT_and_GIFT_RECEIVED_created_for_purchase(
    store_user, user, products, promotions, relate_product_to_store
):
    user.balance = 113.00
    user.save()

    price = relate_product_to_store(products[0], store_user.store)
    data = {
        "user": user.id,
        "amount": 4.00,
        "gift_recipient": store_user.id,
        "products_purchased": [
            {
                "price_id": str(price.id),
                "quantity": 3,
            }
        ],
        "promotions_purchased": [{"id": promotions[0].id, "quantity": 1}],
    }
    purchase_serializer = PurchaseSerializer(data=data)
    purchase_serializer.is_valid(raise_exception=True)
    purchase = purchase_serializer.save()

    mov1 = Movement.objects.get(
        movement_type=Movement.Type.GIFT_SENT.value, purchase=purchase.id
    )
    mov2 = Movement.objects.get(
        movement_type=Movement.Type.GIFT_RECEIVED.value, purchase=purchase.id
    )
    assert mov1.grouping_id == mov2.grouping_id


@pytest.mark.django_db
@patch("stores.serializers.datetime")
def test_GIFT_REFUND_and_GIFT_REJECTED_for_purchase_rejection(datetime_mock, purchase):
    datetime_mock.now.return_value = datetime(2021, 12, 31, tzinfo=timezone.utc)
    data = {"status": Purchase.Status.REJECTED.value}
    purchase_serializer = PurchaseSerializer(purchase, data=data, partial=True)
    purchase_serializer.is_valid(raise_exception=True)
    purchase = purchase_serializer.save()

    mov1 = Movement.objects.get(
        movement_type=Movement.Type.GIFT_REFUNDED, purchase=purchase.id
    )
    mov2 = Movement.objects.get(
        movement_type=Movement.Type.GIFT_REJECTED, purchase=purchase.id
    )
    assert mov1.grouping_id == mov2.grouping_id


@pytest.mark.django_db
def test_GIFT_ACCEPTED_for_purchase_acceptance(purchase):
    data = {"status": Purchase.Status.ACCEPTED.value}
    purchase_serializer = PurchaseSerializer(purchase, data=data, partial=True)
    purchase_serializer.is_valid(raise_exception=True)
    purchase = purchase_serializer.save()

    Movement.objects.filter(
        movement_type=Movement.Type.GIFT_ACCEPTED, purchase=purchase
    ).exists()


@pytest.mark.django_db
@patch("stores.serializers.datetime")
def test_GIFT_REFUND_and_GIFT_EXPIRED_for_purchase_expiration(datetime_mock, purchase):
    datetime_mock.now.return_value = datetime(2022, 1, 2, tzinfo=timezone.utc)
    data = {"status": Purchase.Status.REJECTED.value}
    purchase_serializer = PurchaseSerializer(
        purchase, data=data, partial=True, context={"expire": True}
    )
    purchase_serializer.is_valid(raise_exception=True)
    purchase = purchase_serializer.save()

    mov1 = Movement.objects.get(
        movement_type=Movement.Type.GIFT_REFUNDED.value, purchase=purchase.id
    )
    mov2 = Movement.objects.get(
        movement_type=Movement.Type.GIFT_EXPIRED.value, purchase=purchase.id
    )
    assert mov1.grouping_id == mov2.grouping_id


@pytest.mark.django_db
def test_FUNDING_created_for_funding(user):
    data = {
        "user": user.id,
        "amount": 20.00,
        "purchased_via": "STRIPE",
        "reference": "reference_mock",
        "status": Funding.Status.SUCCESSFUL,
        "fee": 0.00,
        "total_amount": 20.00,
    }
    funding_serializer = FundingSerializer(data=data)
    funding_serializer.is_valid(raise_exception=True)
    funding = funding_serializer.save()

    assert Movement.objects.filter(
        movement_type=Movement.Type.FUNDING.value, funding=funding.id
    ).exists()


@pytest.mark.django_db
def test_GIFT_CLAIMED_and_BAR_CLAIM_PAYMENT_created_for_purchase_delivered(purchase):
    purchase.status = Purchase.Status.CLAIMED
    purchase.save()

    data = {"status": Purchase.Status.DELIVERED.value}
    purchase_update_serializer = PurchaseSerializer(purchase, data=data, partial=True)
    purchase_update_serializer.is_valid(raise_exception=True)
    purchase_update_serializer.save()

    mov1 = Movement.objects.get(
        movement_type=Movement.Type.GIFT_CLAIMED.value, purchase=purchase.id
    )
    mov2 = Movement.objects.get(
        movement_type=Movement.Type.BAR_CLAIM_PAYMENT.value, purchase=purchase.id
    )
    assert mov1.grouping_id == mov2.grouping_id


@pytest.mark.django_db
def test_ADMIN_FUNDING_created_for_admin_deposit(admin_user, fund_account):
    data = {
        "destination_account": fund_account.id,
        "amount": 175.65,
        "usd_exchange_rate": 35.45,
    }
    admin_fund_serializer = FundOperationSerializer(data=data)
    admin_fund_serializer.is_valid(raise_exception=True)
    admin_operation = admin_fund_serializer.save(admin=admin_user)

    queryset = Movement.objects.filter(
        movement_type=Movement.Type.ADMIN_FUNDING.value, admin_operation=admin_operation
    )

    assert queryset.exists()


@pytest.mark.django_db
def test_ADMIN_FUND_WITHDRAWAL_created_for_admin_fund_withdrawal(
    admin_user, fund_account
):
    data = {
        "origin_account": fund_account.id,
        "amount": -2.25,
        "usd_exchange_rate": 35.45,
    }
    admin_fund_serializer = FundOperationSerializer(data=data)
    admin_fund_serializer.is_valid(raise_exception=True)
    admin_operation = admin_fund_serializer.save(admin=admin_user)

    assert Movement.objects.filter(
        movement_type=Movement.Type.ADMIN_FUNDS_WITHDRAWAL.value,
        admin_operation=admin_operation,
    ).exists()


@pytest.mark.django_db
def test_ADMIN_BAR_PAYMENT_created_for_admin_bar_payment(store, purchase, fund_account):
    purchase.status = Purchase.Status.DELIVERED
    purchase.amount = 10.0
    purchase.save()

    png = SimpleUploadedFile("tiny.png", b"valid_png_bin")
    data = {
        "store": store.id,
        "amount": 10.0 * (1 - store.commission_percentage),
        "receipt": png,
        "funds_account_origin": fund_account.id,
        "usd_exchange_rate": 10.0,
    }
    bar_payment = AdminStorePaymentSerializer(data=data)
    bar_payment.is_valid(raise_exception=True)
    bar_payment = bar_payment.save()

    assert Movement.objects.filter(
        movement_type=Movement.Type.ADMIN_BAR_PAYMENT.value, store_payment=bar_payment
    ).exists()
    bar_payment.receipt.delete()


@pytest.mark.django_db
def test_FUNDS_EXCHANGE_created_for_admin_funds_transfer(admin_user, fund_accounts):
    data = {
        "origin_account": fund_accounts[0].id,
        "destination_account": fund_accounts[1].id,
        "amount": 5.78,
        "usd_exchange_rate": 35.45,
    }
    operation_serializer = FundOperationSerializer(data=data)
    operation_serializer.is_valid(raise_exception=True)
    operation = operation_serializer.save(admin=admin_user)

    mov1 = Movement.objects.get(
        movement_type=Movement.Type.FUNDS_EXCHANGE_ORIGIN.value,
        admin_operation=operation,
    )
    mov2 = Movement.objects.get(
        movement_type=Movement.Type.FUNDS_EXCHANGE_DESTINATION.value,
        admin_operation=operation,
    )
    assert mov1.grouping_id == mov2.grouping_id
