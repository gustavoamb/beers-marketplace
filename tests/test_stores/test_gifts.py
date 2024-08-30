from datetime import datetime, timezone
from unittest.mock import patch
from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from stores.models import Purchase, get_gift_expiration_date

client = APIClient()


@patch("stores.models.datetime")
def test_get_gift_expiration_date(datetime_mock):
    datetime_mock.now.return_value = datetime(2022, 1, 1, tzinfo=timezone.utc)
    expiration_date = get_gift_expiration_date()

    assert expiration_date == datetime(2022, 1, 4, tzinfo=timezone.utc)


@patch("stores.models.datetime")
def test_gift_purchase_not_expired(datetime_mock, purchase):
    datetime_mock.now.return_value = datetime(2021, 12, 31, tzinfo=timezone.utc)
    assert not purchase.gift_has_expired


@patch("stores.models.datetime")
def test_gift_purchase_expired(datetime_mock, purchase):
    datetime_mock.now.return_value = datetime(2022, 1, 2, tzinfo=timezone.utc)
    assert purchase.gift_has_expired


@patch(
    "stores.serializers.PurchaseNotificationHelper._PurchaseNotificationHelper__create_notification"
)
def test_gift_rejected_amount_refunded_to_sender(notif_helper_mock, user, purchase):
    assert user.balance == 0.0

    payload = {"status": Purchase.Status.REJECTED.value}
    client.force_authenticate(user=user)
    url = reverse("purchase-reject-gift", kwargs={"pk": purchase.id})
    response = client.patch(url, payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    assert user.balance == Decimal(str(13.18))
