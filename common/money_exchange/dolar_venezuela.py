import os
import requests

from decimal import Decimal
from datetime import datetime
from pytz import timezone

from users.models import SystemCurrency


class PyDolarVenezuelaService:
    def __init__(self):
        self._api_url = os.getenv("PY_DOLAR_VENEZUELA_API_URL")

    def get_dollar_exchange_rates(self):
        response = requests.get(f"{self._api_url}/api/v1/dollar/")
        monitors = response.json()["monitors"]
        return monitors

    def get_dollar_exchange_from_page(self, page):
        params = {"page": page, "monitor": "usd"}
        response = requests.get(f"{self._api_url}/api/v1/dollar/page", params=params)
        print(response)
        price = response.json()["price"]
        return price


class USDtoVES:
    def __init__(self, usd_exchange_api):
        self.usd_api: PyDolarVenezuelaService = usd_exchange_api
        # We want the service to always fetch the initial api_rate when initialized,
        # thus we set this to always a little bit before 9 AM of the current date, since
        # Venezuela's dollar APIs refresh at 9 AM.
        self.api_rate = None

    def get_usd_exchange_rate(self):
        today_at_9_am = datetime.now(tz=timezone("America/Caracas")).replace(
            hour=9, minute=0, second=0
        )
        try:
            system_usd = SystemCurrency.objects.get(
                iso_code="USD",
            )
            return system_usd.ves_exchange_rate
        except:
            if self.api_rate:
                return self.api_rate

            return self.fetch_and_set_api_rate()

    def fetch_and_set_api_rate(self):
        api_exchange_rate = self.usd_api.get_dollar_exchange_from_page("bcv")
        self.api_rate = Decimal(str(api_exchange_rate))
        return self.api_rate


dolar_venezuela_service = PyDolarVenezuelaService()
usd_exchange_rate_service = USDtoVES(dolar_venezuela_service)
