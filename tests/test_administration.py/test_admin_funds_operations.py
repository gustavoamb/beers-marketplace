import pytest

from decimal import Decimal, ROUND_DOWN
from unittest.mock import patch

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from common.utils import round_to_fixed_exponent

from administration.models import FundAccount, FundOperation


client = APIClient()


@pytest.fixture
def make_fund_operation(admin_user, make_fund_account):
    def __make_fund_operation(data=None):
        if data is None:
            origin = make_fund_account({"name": "Origin Test"})
            dest = make_fund_account({"name": "Destination Test"})
            data = {
                "admin": admin_user,
                "amount": 100.0,
                "origin_account": origin,
                "destination_account": dest,
                "usd_exchange_rate": 1.0,
                "commission": 0.0,
            }

        return FundOperation.objects.create(**data)

    return __make_fund_operation


@pytest.mark.django_db
@patch(
    "administration.serializers.FundOperationSerializerHelper.create_related_movements",
)
def test_deposit_creation(helper_method_mock, admin_user, fund_account):
    payload = {
        "destination_account": fund_account.id,
        "amount": 1200.87,
        "usd_exchange_rate": 100,
    }

    client.force_authenticate(user=admin_user)
    url = reverse("fundoperation-list")
    response = client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED

    old_balance = fund_account.balance
    fund_account.refresh_from_db()
    assert fund_account.balance == Decimal(str(old_balance + payload["amount"]))
    helper_method_mock.assert_called_once()


@pytest.mark.django_db
def test_withdrawal_creation(admin_user, fund_account):
    payload = {
        "origin_account": fund_account.id,
        "amount": -19.99,
        "usd_exchange_rate": 100,
    }

    client.force_authenticate(user=admin_user)
    url = reverse("fundoperation-list")
    response = client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED

    old_balance = fund_account.balance
    fund_account.refresh_from_db()
    assert fund_account.balance == Decimal(old_balance + payload["amount"]).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )


@pytest.mark.django_db
def test_fund_withdrawal_creation_invalid_amount(admin_user, fund_account):
    payload = {
        "origin_account": fund_account.id,
        "amount": -25.00,
        "usd_exchange_rate": 100,
    }

    client.force_authenticate(user=admin_user)
    url = reverse("fundoperation-list")
    response = client.post(url, payload, format="json")
    data = response.data
    expectedErrorMsg = (
        "Insufficient balance in origin fund account to perform operation."
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert data["amount_&_origin_account"][0] == expectedErrorMsg


@pytest.mark.django_db
def test_fund_exchange_creation(admin_user, fund_accounts):
    origin_acc = fund_accounts[0]
    dest_acc = fund_accounts[1]
    payload = {
        "origin_account": origin_acc.id,
        "destination_account": dest_acc.id,
        "amount": 12.50,
        "usd_exchange_rate": 100,
    }
    client.force_authenticate(user=admin_user)
    url = reverse("fundoperation-list")
    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    origin_old_balance = origin_acc.balance
    origin_acc.refresh_from_db()
    assert origin_acc.balance == round_to_fixed_exponent(
        origin_old_balance - payload["amount"]
    )

    dest_old_balance = dest_acc.balance
    dest_acc.refresh_from_db()
    assert dest_acc.balance == round_to_fixed_exponent(
        dest_old_balance + payload["amount"]
    )

    assert response.data["usd_exchange_rate"] == "1.00"


@pytest.mark.django_db
def test_fund_exchange_origin_USD_dest_VES(admin_user, fund_accounts):
    origin_acc = fund_accounts[0]
    dest_acc = fund_accounts[1]
    dest_acc.currency = FundAccount.Currency.VES.value
    dest_acc.save()

    payload = {
        "origin_account": origin_acc.id,
        "destination_account": dest_acc.id,
        "amount": 12.50,
        "usd_exchange_rate": 10.0,
    }
    client.force_authenticate(user=admin_user)
    url = reverse("fundoperation-list")
    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    origin_old_balance = origin_acc.balance
    origin_acc.refresh_from_db()
    assert origin_acc.balance == round_to_fixed_exponent(
        origin_old_balance - payload["amount"]
    )

    dest_old_balance = dest_acc.balance
    dest_acc.refresh_from_db()
    assert dest_acc.balance == round_to_fixed_exponent(
        dest_old_balance + (payload["amount"] * 10.0)
    )


@pytest.mark.django_db
def test_fund_exchange_origin_VES_dest_USD(admin_user, fund_accounts):
    origin_acc = fund_accounts[0]
    origin_acc.currency = FundAccount.Currency.VES.value
    origin_acc.save()
    dest_acc = fund_accounts[1]

    usd_exchange_rate = 10.0
    commission = 100
    payload = {
        "origin_account": origin_acc.id,
        "destination_account": dest_acc.id,
        "amount": 12.50,
        "usd_exchange_rate": usd_exchange_rate,
        "commission": commission,
    }
    client.force_authenticate(user=admin_user)
    url = reverse("fundoperation-list")
    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    origin_old_balance = origin_acc.balance
    origin_acc.refresh_from_db()
    assert origin_acc.balance == round_to_fixed_exponent(
        origin_old_balance - payload["amount"]
    )

    dest_old_balance = dest_acc.balance
    dest_acc.refresh_from_db()
    assert dest_acc.balance == Decimal(
        dest_old_balance + (payload["amount"] / usd_exchange_rate) - commission
    )


@pytest.mark.django_db
def test_VES_deposit_computed_amounts(
    make_fund_account, admin_user, make_fund_operation
):
    destination = make_fund_account({"currency": FundAccount.Currency.VES})
    amount_local_currency = 6520.25
    usd_exchange_rate = 100.0
    amount_usd = amount_local_currency / usd_exchange_rate
    deposit_data = {
        "admin": admin_user,
        "amount": amount_local_currency,
        "destination_account": destination,
        "usd_exchange_rate": usd_exchange_rate,
    }
    deposit = make_fund_operation(deposit_data)
    assert deposit.amount_local_currency == amount_local_currency
    assert deposit.amount_usd == round_to_fixed_exponent(amount_usd)


@pytest.mark.django_db
def test_USD_deposit_computed_amounts(
    make_fund_account, admin_user, make_fund_operation
):
    destination = make_fund_account({"currency": FundAccount.Currency.USD})
    amount_usd = 6520.25
    usd_exchange_rate = 100.0
    amount_local_currency = amount_usd * usd_exchange_rate
    deposit_data = {
        "admin": admin_user,
        "amount": amount_usd,
        "destination_account": destination,
        "usd_exchange_rate": usd_exchange_rate,
    }
    deposit = make_fund_operation(deposit_data)
    assert deposit.amount_local_currency == amount_local_currency
    assert deposit.amount_usd == amount_usd


@pytest.mark.django_db
def test_VES_withdrawal_computed_amounts(
    make_fund_account, admin_user, make_fund_operation
):
    origin = make_fund_account({"currency": FundAccount.Currency.VES})
    amount_local_currency = 6520.25
    usd_exchange_rate = 100.0
    amount_usd = amount_local_currency / usd_exchange_rate
    withdrawal_data = {
        "admin": admin_user,
        "amount": amount_local_currency,
        "origin_account": origin,
        "usd_exchange_rate": usd_exchange_rate,
    }
    withdrawal = make_fund_operation(withdrawal_data)
    assert withdrawal.amount_local_currency == amount_local_currency
    assert withdrawal.amount_usd == round_to_fixed_exponent(amount_usd)


@pytest.mark.django_db
def test_USD_withdrawal_computed_amounts(
    make_fund_account, admin_user, make_fund_operation
):
    origin = make_fund_account({"currency": FundAccount.Currency.USD})
    amount_usd = 6520.25
    usd_exchange_rate = 100.0
    amount_local_currency = amount_usd * usd_exchange_rate
    withdrawal_data = {
        "admin": admin_user,
        "amount": amount_usd,
        "origin_account": origin,
        "usd_exchange_rate": usd_exchange_rate,
    }
    withdrawal = make_fund_operation(withdrawal_data)
    assert withdrawal.amount_local_currency == amount_local_currency
    assert withdrawal.amount_usd == round_to_fixed_exponent(amount_usd)


@pytest.mark.django_db
def test_VES_to_USD_exchange_computed_amounts(
    make_fund_account, admin_user, make_fund_operation
):
    origin = make_fund_account({"currency": FundAccount.Currency.VES})
    destination = make_fund_account({"currency": FundAccount.Currency.USD})
    amount_local_currency = 6520.25
    usd_exchange_rate = 100.0
    amount_usd = amount_local_currency / usd_exchange_rate
    exchange_data = {
        "admin": admin_user,
        "amount": amount_local_currency,
        "origin_account": origin,
        "destination_account": destination,
        "usd_exchange_rate": usd_exchange_rate,
    }
    exchange = make_fund_operation(exchange_data)
    assert exchange.amount_local_currency == amount_local_currency
    assert exchange.amount_usd == round_to_fixed_exponent(amount_usd)


@pytest.mark.django_db
def test_USD_to_VES_exchange_computed_amounts(
    make_fund_account, admin_user, make_fund_operation
):
    origin = make_fund_account({"currency": FundAccount.Currency.USD})
    destination = make_fund_account({"currency": FundAccount.Currency.VES})
    amount_usd = 6520.25
    usd_exchange_rate = 100.0
    amount_local_currency = amount_usd * usd_exchange_rate
    exchange_data = {
        "admin": admin_user,
        "amount": amount_usd,
        "origin_account": origin,
        "destination_account": destination,
        "usd_exchange_rate": usd_exchange_rate,
    }
    exchange = make_fund_operation(exchange_data)
    assert exchange.amount_local_currency == amount_local_currency
    assert exchange.amount_usd == amount_usd
