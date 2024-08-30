import os
import requests
import json

from enum import Enum
from rest_framework import status

from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session

from common.payments.interfaces.customer import Customer
from common.payments.interfaces.payments import PaymentServiceInterface
from common.payments.interfaces.payment_information import (
    PaymentInformation,
    TransactionCapture,
)


class PaypalOrderIntent(Enum):
    CAPTURE = "CAPTURE"
    AUTHORIZE = "AUTHORIZE"


class OrderError:
    def __init__(self, response_data):
        self.name = response_data["name"]
        self.issue = response_data["details"][0]["issue"]
        self.description = response_data["details"][0]["description"]

    def get_error_msg(self):
        return f"${self.issue}: {self.description}"


class PaypalService(PaymentServiceInterface):
    def __init__(self):
        self._api_url = os.getenv("PAYPAL_API_URL")
        self._app_client_id = os.getenv("PAYPAL_APP_CLIENT_ID")
        self._app_client_secret = os.getenv("PAYPAL_APP_SECRET")

        client = BackendApplicationClient(client_id=self._app_client_id)
        self.oauth = OAuth2Session(client=client)
        self._api_access_token = None

    def get_and_set_api_access_token(self):
        get_access_token_url = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
        response = self.oauth.fetch_token(
            token_url=get_access_token_url,
            client_id=self._app_client_id,
            client_secret=self._app_client_secret,
            kwargs={"grant_type": "client_credentials"},
        )
        self._api_access_token = response["access_token"]

    def create_customer(self, customer: Customer):
        return None

    def create_payment(self, payment_information: PaymentInformation):
        url = f"{self._api_url}/checkout/orders"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_access_token}",
        }
        beers_purchase_amount = payment_information.amount
        payload = {
            "intent": PaypalOrderIntent.CAPTURE.value,
            "purchase_units": [
                {"amount": {"currency_code": "USD", "value": beers_purchase_amount}}
            ],
        }
        payload_json = json.dumps(payload)
        try:
            response = requests.post(url, headers=headers, data=payload_json)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                # Access token expired, attempt refresh.
                self.get_and_set_api_access_token()
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_access_token}",
                }
                response = requests.post(url, headers=headers, data=payload_json)
                response.raise_for_status()

        return response.json()

    def capture_payment(self, transaction: TransactionCapture):
        url = f"{self._api_url}/checkout/orders/{transaction.id}/capture"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_access_token}",
        }
        simulate_failure = bool(os.getenv("PAYPAL_SIMULATE_FAILURE", False))
        if simulate_failure:
            headers["PayPal-Mock-Response"] = str(
                {"mock_application_codes": "DUPLICATE_INVOICE_ID"}
            )

        try:
            response = requests.post(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != status.HTTP_401_UNAUTHORIZED:
                raise e

            # Access token expired, attempt refresh.
            self.get_and_set_api_access_token()
            headers["Authorization"] = f"Bearer {self._api_access_token}"
            response = requests.post(url, headers=headers)
            response.raise_for_status()

        return response.json()

    def show_order_details(self, order_id):
        url = f"{self._api_url}/checkout/orders/{order_id}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_access_token}",
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        return response.json()


paypal_service = PaypalService()
