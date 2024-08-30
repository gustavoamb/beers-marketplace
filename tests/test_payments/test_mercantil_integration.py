from unittest.mock import patch, Mock, MagicMock
from decimal import Decimal

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate, APIClient

from payments.models import Funding

from payments.views import ConfirmMercantilMobilePaymentView

from administration.models import FundAccount

from .mercantil_sample_data import (
    mobile_payments_not_found_response,
    mobile_payments_success_response,
)
from .pydolarevenezuela_sample_data import page_dollar_price_success_response

request_factory = APIRequestFactory()
client = APIClient()


@patch("common.money_exchange.dolar_venezuela.requests")
@patch("common.payments.services.mercantil.requests.session")
def test_confirm_mobile_payment_not_found(
    requests_session_mock, exchange_requests_mock, user
):
    requests_post_response_mock = Mock()
    requests_post_response_mock.json.return_value = mobile_payments_not_found_response
    session_post_mock = MagicMock()
    session_post_mock.post.return_value = requests_post_response_mock
    requests_session_mock.return_value = session_post_mock

    requests_get_response_mock = Mock()
    requests_get_response_mock.json.return_value = page_dollar_price_success_response
    exchange_requests_mock.get.return_value = requests_get_response_mock

    payload = {
        "amount": 12.00,
        "origin_mobile_number": "encrypted-mobile-number",
        "destination_mobile_number": "encrypted-destination-number",
        "payment_reference": 927660007532,
        "trx_date": "2023-10-03",
    }
    request = request_factory.post(f"beers/mobile-payments/mercantil", data=payload)
    force_authenticate(request, user)
    view = ConfirmMercantilMobilePaymentView.as_view()
    response = view(request)
    funding = response.data
    expectedError = "No hay transacciones que coincidan con los campos de busqueda"
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert funding["status"] == Funding.Status.FAILED.value
    assert funding["error"] == expectedError


@patch("payments.api.fulfill_orders.usd_exchange_rate_service")
@patch("common.payments.services.mercantil.requests.session")
def test_confirm_mobile_payment_success(
    requests_session_mock, exchange_service_mock, user, make_fund_account
):
    mercantil_acc = make_fund_account(
        {"name": "Mercantil", "currency": FundAccount.Currency.VES}
    )

    requests_post_response_mock = Mock()
    requests_post_response_mock.json.return_value = mobile_payments_success_response
    session_post_mock = MagicMock()
    session_post_mock.post.return_value = requests_post_response_mock
    requests_session_mock.return_value = session_post_mock

    exchange_service_mock.get_usd_exchange_rate.return_value = Decimal(
        str(page_dollar_price_success_response["price"])
    )

    payload = {
        "amount": 3333.0,
        "origin_mobile_number": "encrypted-mobile-number",
        "destination_mobile_number": "encrypted-destination-number",
        "payment_reference": 118060003823,
        "trx_date": "2021-06-29",
    }

    client.force_authenticate(user=user)
    url = reverse("mercantil-confirm-order")
    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    assert user.balance == 0
    user.refresh_from_db()

    funding = response.data
    assert funding["user"] == user.id

    usd_exchange = page_dollar_price_success_response["price"]
    assert funding["total_amount"] == round(
        Decimal(payload["amount"] / usd_exchange),
        2,
    )
    assert funding["purchased_via"] == Funding.PaymentPlatform.MERCANTIL_PAGO_MOVIL
    assert funding["reference"] == str(
        mobile_payments_success_response["transaction_list"][0]["payment_reference"]
    )

    mercantil_acc.refresh_from_db()
    assert mercantil_acc.balance == payload["amount"]
