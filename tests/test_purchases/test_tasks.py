import pytest

from datetime import datetime
from pytz import timezone
from unittest.mock import patch

from stores.models import Purchase
from stores.tasks import expire_purchases


@pytest.mark.django_db
@patch("users.serializers.add_funds_to_customer")
@patch("stores.serializers.PurchaseNotificationHelper")
@patch("stores.tasks.datetime")
def test_expire_purchases(
    datetime_mock, helper_mock, add_funds_to_customer_mock, purchases_v2
):
    datetime_mock.now.return_value = datetime(
        2022, 1, 2, tzinfo=timezone("America/Caracas")
    )

    purchases_updated = expire_purchases()

    assert len(purchases_updated) == len((purchases_v2))
    assert all([p.status == Purchase.Status.REJECTED.value for p in purchases_updated])
    assert add_funds_to_customer_mock.call_count == 10
