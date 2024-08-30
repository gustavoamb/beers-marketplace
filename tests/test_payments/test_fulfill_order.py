import pytest
from decimal import Decimal

from payments.api.fulfill_orders import add_funds_to_customer


@pytest.mark.django_db
def test_add_funds_to_customer(user):
    assert user.balance == 0

    amount_1 = 15.25
    add_funds_to_customer(user.id, amount_1)
    user.refresh_from_db()
    assert user.balance == Decimal(str(amount_1))

    amount_2 = 42.37
    add_funds_to_customer(user.id, amount_2)
    user.refresh_from_db()
    assert user.balance == Decimal(str(amount_1)) + Decimal(str(amount_2))
