import pytest
from datetime import datetime, timezone
from decimal import Decimal, ROUND_UP
from unittest.mock import patch

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIRequestFactory, force_authenticate

from stores.views import PurchaseViewSet, StoreViewSet

from common.permissions import IsAdminOrVerifiedStoreUser

client = APIClient()


@pytest.mark.django_db
@patch("stores.serializers.datetime")
def test_get_stores_balances_admin(datetime_mock, admin_user, store, purchases):
    datetime_mock.now.return_value = datetime(2022, 12, 31, tzinfo=timezone.utc)

    client.force_authenticate(user=admin_user)
    url = reverse("admin-stores-balance")
    response = client.get(url)
    results = response.data["results"]

    assert response.status_code == status.HTTP_200_OK
    assert results[0]["id"] == store.id

    commission = Decimal(store.commission_percentage)
    amount = purchases[1].amount * (Decimal(1) - commission)

    expected_balance = float((amount).quantize(Decimal("0.0001"), rounding=ROUND_UP))
    received_balance = float(results[0]["balance"])
    assert received_balance == expected_balance


@pytest.mark.django_db
def test_get_stores_balances_person_user_permissions(user):
    client.force_authenticate(user=user)
    url = reverse("admin-stores-balance")
    response = client.get(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_get_stores_balance_store_user_permissions(store):
    client.force_authenticate(user=store.user)
    url = reverse("admin-stores-balance")
    response = client.get(url)

    assert response.status_code == status.HTTP_403_FORBIDDEN
