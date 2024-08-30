from unittest.mock import patch, Mock
from requests.exceptions import HTTPError

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from payments.models import Funding

from .paypal_sample_data import (
    capture_order_sample_response,
    order_details_sample,
    capture_order_error,
)

client = APIClient()


@patch("common.payments.services.paypal.requests")
def test_capture_paypal_order(requests_mock, user, make_fund_account):
    paypal_acc = make_fund_account({"name": "Paypal"})

    capture_order_sample_response["purchase_units"][0]["payments"]["captures"][0][
        "custom_id"
    ] = user.id
    requests_post_response_mock = Mock()
    requests_post_response_mock.json.return_value = capture_order_sample_response
    requests_mock.post.return_value = requests_post_response_mock

    paypal_order_id = "fake_id"
    url = reverse("paypal-capture-order", kwargs={"paypal_order_id": paypal_order_id})
    response = client.post(url)
    data = response.data
    assert response.status_code == status.HTTP_201_CREATED
    assert len(data) == 1
    assert user.balance == 0
    user.refresh_from_db()

    funding = data[0]
    assert funding["user"] == user.id
    assert funding["total_amount"] == user.balance
    assert funding["purchased_via"] == Funding.PaymentPlatform.PAYPAL
    assert funding["status"] == Funding.Status.SUCCESSFUL
    assert funding["reference"] == capture_order_sample_response["id"]

    paypal_acc.refresh_from_db()
    assert paypal_acc.balance == funding["total_amount"]


@patch("common.payments.services.paypal.requests")
def test_capture_failed_order(requests_mock, user):
    requests_mock.exceptions.HTTPError = HTTPError
    post_response_mock = Mock()
    post_response_mock.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    post_response_mock.json.return_value = capture_order_error

    post_response_mock.raise_for_status = Mock(
        side_effect=HTTPError(response=post_response_mock)
    )
    requests_mock.post.return_value = post_response_mock

    order_details_sample["purchase_units"][0]["custom_id"] = user.id
    get_response_mock = Mock()
    get_response_mock.json.return_value = order_details_sample
    requests_mock.get.return_value = get_response_mock

    paypal_order_id = "fake_id"
    url = reverse("paypal-capture-order", kwargs={"paypal_order_id": paypal_order_id})
    response = client.post(url)
    assert response.status_code == status.HTTP_201_CREATED

    funding = response.data[0]
    assert funding["user"] == user.id
    assert funding["purchased_via"] == Funding.PaymentPlatform.PAYPAL
    assert funding["status"] == Funding.Status.FAILED
    assert funding["reference"] == order_details_sample["id"]

    old_balance = user.balance
    user.refresh_from_db()
    new_balance = user.balance
    assert old_balance == new_balance
    assert new_balance == 0
