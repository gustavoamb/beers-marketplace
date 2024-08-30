import pytest

from uuid import UUID
from unittest.mock import patch

from django.urls import reverse

from stripe import error as stripe_errors

from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate, APIClient

from payments.models import Funding, RechargeFundsSession
from payments.views import RechargeViaStripeView, StripeWebhook

from common.payments.services.stripe import stripe_service

from .stripe_sample_data import payment_intent_sample

request_factory = APIRequestFactory()
client = APIClient()


@pytest.fixture
def recharge_session(user):
    session = RechargeFundsSession.objects.create(
        user=user,
        payment_platform=Funding.PaymentPlatform.STRIPE,
        order=payment_intent_sample.id,
        request_idempotency_key=UUID("2e1a104c-7820-4062-af76-54579c2ee91c"),
    )
    return session


@pytest.fixture
def make_recharge_funds_session(user):
    def __recharge_funds_session(data=None):
        boilerplate_data = {
            "user": user,
            "order": payment_intent_sample.id,
            "request_idempotency_key": UUID("2e1a104c-7820-4062-af76-54579c2ee91c"),
        }
        if data is not None:
            boilerplate_data.update(**data)

        data = boilerplate_data
        return RechargeFundsSession.objects.create(**data)

    return __recharge_funds_session


@pytest.mark.django_db
@patch("payments.views.stripe_service")
def test_recharge_via_stripe(stripe_service_mock, user):
    stripe_service_mock.create_payment.return_value = payment_intent_sample

    payload = {"amount": 20}
    request = request_factory.post("recharges/stripe/", data=payload)
    force_authenticate(request, user)
    view = RechargeViaStripeView.as_view()
    response = view(request)
    data = response.data

    assert response.status_code == status.HTTP_200_OK
    assert data["payment_intent"].id == payment_intent_sample.id


def test_recharge_via_stripe_invalid_amount(user):
    payload = {"amount": 9.99}
    request = request_factory.post("recharges/stripe/", data=payload)
    force_authenticate(request, user)
    view = RechargeViaStripeView.as_view()
    response = view(request)
    data = response.data

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert data["amount"] == "Monto mínimo de recarga: 20.0"


@pytest.mark.django_db
@patch("payments.views.stripe_service")
def test_recharge_via_stripe_create_session(stripe_service_mock, user):
    stripe_service_mock.create_payment.return_value = payment_intent_sample

    payload = {"amount": 20}
    request = request_factory.post("recharges/stripe/", data=payload)
    force_authenticate(request, user)
    view = RechargeViaStripeView.as_view()
    view(request)

    sessions_in_progress = RechargeFundsSession.objects.filter(
        user=user.id, status=RechargeFundsSession.Status.IN_PROGRESS
    )
    assert sessions_in_progress.count() == 1
    session = sessions_in_progress.latest("updated_at")
    assert session.payment_platform == Funding.PaymentPlatform.STRIPE
    assert session.order == payment_intent_sample.id


@pytest.mark.django_db
@patch("payments.views.stripe_service")
def test_recharge_via_stripe_continue_session(
    stripe_service_mock, user, recharge_session
):
    payload = {"amount": 20}
    request = request_factory.post("recharges/stripe/", data=payload)
    force_authenticate(request, user)
    view = RechargeViaStripeView.as_view()
    view(request)

    sessions_in_progress = RechargeFundsSession.objects.filter(
        user=user.id, status=RechargeFundsSession.Status.IN_PROGRESS
    )
    assert sessions_in_progress.count() == 1
    session = sessions_in_progress.latest("updated_at")
    assert session.id == recharge_session.id
    assert session.payment_platform == Funding.PaymentPlatform.STRIPE
    assert session.order == payment_intent_sample.id


@pytest.mark.django_db
@patch("payments.views.stripe_service")
def test_recharge_via_stripe_update_order_amount(
    stripe_service_mock, user, recharge_session
):
    stripe_service_mock.create_payment.return_value = payment_intent_sample
    payload = {"amount": 50}
    request = request_factory.post("recharges/stripe/", data=payload)
    force_authenticate(request, user)
    view = RechargeViaStripeView.as_view()
    response = view(request)

    assert response.status_code == status.HTTP_200_OK
    stripe_service_mock.update_payment.assert_called


@pytest.mark.django_db
@patch("payments.views.stripe_service")
def test_webhook_successful_payment(stripe_service_mock, user, make_fund_account):
    stripe_service_mock.capture_payment.return_value = payment_intent_sample
    stripe_service_mock.get_payment_fee = stripe_service.get_payment_fee

    stripe_fee = stripe_service.get_payment_fee(payment_intent_sample.amount / 100)

    stripe_acc = make_fund_account({"name": "stripe"})

    request = request_factory.post("beers/stripe/webhook/")
    view = StripeWebhook.as_view()
    response = view(request)

    assert response.status_code == status.HTTP_201_CREATED

    assert user.balance == 0
    user.refresh_from_db()
    funding = Funding.objects.get(reference=payment_intent_sample.id)
    assert funding.user == user
    assert funding.total_amount - stripe_fee == user.balance
    assert funding.purchased_via == Funding.PaymentPlatform.STRIPE
    assert funding.status == Funding.Status.SUCCESSFUL

    stripe_acc.refresh_from_db()
    stripe_acc.balance == funding.total_amount


@pytest.mark.django_db
@patch("payments.views.stripe_service")
def test_payment_intent_confirm_failed(stripe_service_mock, recharge_session, user):
    stripe_error = stripe_errors.StripeError("stripe error message")
    stripe_service_mock.confirm_payment.side_effect = stripe_error
    stripe_service_mock.get_payment.return_value = payment_intent_sample
    stripe_service_mock.get_payment_fee.return_value = 15.0

    url = reverse("stripe-confirm", kwargs={"session_id": recharge_session.id})
    client.force_authenticate(user=user)
    payload = {"payment_method_id": recharge_session.order}
    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["message"] == stripe_error.user_message
