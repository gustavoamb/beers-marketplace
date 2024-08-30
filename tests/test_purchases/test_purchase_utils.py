import pytest

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from stores.models import Purchase


def test_get_purchase_info_template(purchase):
    purchase.gift_expiration_date = datetime.now(timezone.utc) + timedelta(days=1)
    purchase.status = Purchase.Status.ACCEPTED
    purchase.save()
    template_name = purchase.information_template
    expected_name = "qr-template/activeOrder.html"
    assert template_name == expected_name


@pytest.mark.django_db
@patch("stores.models.datetime")
def test_get_delivered_purchase_info_template(datetime_mock, purchase):
    datetime_mock.now.return_value = datetime(2021, 12, 31, tzinfo=timezone.utc)
    purchase.gift_expiration_date = datetime.now(timezone.utc) + timedelta(days=1)
    purchase.status = Purchase.Status.CLAIMED
    purchase.save()
    template_name = purchase.information_template
    expected_name = "qr-template/deliveredOrder.html"
    assert template_name == expected_name


@patch("stores.models.datetime")
def test_get_expired_purchase_info_template(datetime_mock, purchase):
    datetime_mock.now.return_value = datetime(2022, 1, 2, tzinfo=timezone.utc)
    template_name = purchase.information_template
    expected_name = "qr-template/expiredOrder.html"
    assert template_name == expected_name
