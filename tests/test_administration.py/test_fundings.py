import pytest
from unittest.mock import patch

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from payments.models import Funding

client = APIClient()


@pytest.mark.django_db
@patch("payments.serializers.FundingSerializer.get_payment_method")
def test_force_funding_stripe(
    get_payment_method_mock,
    make_fund_account,
    admin_user,
    funding,
    user,
):
    get_payment_method_mock.return_value = {"card": "**** **** **** 1234"}

    account = make_fund_account({"name": "Stripe", "currency": "USD"})

    funding.status = Funding.Status.FAILED
    funding.save()

    client.force_authenticate(user=admin_user)
    url = reverse("admin-force-funding", kwargs={"funding_id": funding.id})
    response = client.patch(url, {}, format="json")
    data = response.data
    assert response.status_code == status.HTTP_200_OK
    assert data["status"] == Funding.Status.SUCCESSFUL.value

    old_balance = user.balance
    user.refresh_from_db()
    new_balance = user.balance
    assert new_balance == old_balance + funding.amount

    account.refresh_from_db()
    assert account.balance == funding.amount


@pytest.mark.django_db
@patch("payments.serializers.FundingSerializer.get_payment_method")
def test_force_funding_paypal(
    get_payment_method_mock,
    make_fund_account,
    admin_user,
    make_funding,
    user,
):
    get_payment_method_mock.return_value = {"card": "**** **** **** 1234"}

    account = make_fund_account({"name": "Paypal", "currency": "USD"})
    funding = make_funding(
        {
            "purchased_via": Funding.PaymentPlatform.PAYPAL,
            "status": Funding.Status.FAILED,
        }
    )

    client.force_authenticate(user=admin_user)
    url = reverse("admin-force-funding", kwargs={"funding_id": funding.id})
    response = client.patch(url, {}, format="json")
    data = response.data
    assert response.status_code == status.HTTP_200_OK
    assert data["status"] == Funding.Status.SUCCESSFUL.value

    old_balance = user.balance
    user.refresh_from_db()
    new_balance = user.balance
    assert new_balance == old_balance + funding.amount

    account.refresh_from_db()
    assert account.balance == funding.amount


@pytest.mark.django_db
@patch("payments.serializers.FundingSerializer.get_payment_method")
def test_force_funding_mercantil(
    get_payment_method_mock,
    make_fund_account,
    admin_user,
    make_funding,
    user,
):
    get_payment_method_mock.return_value = {"card": "**** **** **** 1234"}

    account = make_fund_account({"name": "Mercantil", "currency": "USD"})
    funding = make_funding(
        {
            "purchased_via": Funding.PaymentPlatform.MERCANTIL_PAGO_MOVIL,
            "status": Funding.Status.FAILED,
            "usd_exchange_rate": 10.0,
        }
    )

    client.force_authenticate(user=admin_user)
    url = reverse("admin-force-funding", kwargs={"funding_id": funding.id})
    response = client.patch(url, {}, format="json")
    data = response.data
    assert response.status_code == status.HTTP_200_OK
    assert data["status"] == Funding.Status.SUCCESSFUL.value

    old_balance = user.balance
    user.refresh_from_db()
    new_balance = user.balance
    assert new_balance == old_balance + funding.amount

    account.refresh_from_db()
    assert account.balance == funding.amount_local_currency
