import pytest
from decimal import Decimal

from unittest.mock import patch, Mock

from common.payments.services.stripe import StripeService, StripePaymentMethods


@pytest.fixture(scope="session", autouse=True)
def stripe_mock():
    with patch("common.payments.services.stripe.stripe") as _fixture:
        yield _fixture


def test_create_customer(stripe_mock):
    response_mock = Mock()
    response_mock.id = "fake_customer_id"
    stripe_mock.Customer.create.return_value = response_mock

    stripe_service = StripeService()
    payload = {"email": "test@test.com"}
    stripe_customer = stripe_service.create_customer(payload)

    stripe_mock.Customer.create.assert_called_once()
    assert stripe_customer.id == response_mock.id


def test_create_setup_intent(stripe_mock):
    expected_response = "fake_setup_intent"
    stripe_mock.SetupIntent.create.return_value = expected_response

    stripe_service = StripeService()
    setup_intent = stripe_service.create_setup_intent("fake_customer_id")

    stripe_mock.SetupIntent.create.assert_called_once()
    assert setup_intent == expected_response


def test_get_payment_fee(stripe_mock):
    stripe_service = StripeService()

    payment_base_amount = 100.0
    fee = stripe_service.get_payment_fee(payment_base_amount)
    assert fee == Decimal("3.29")
