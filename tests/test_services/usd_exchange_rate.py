import pytest

from decimal import Decimal
from datetime import datetime, timezone
from pytz import timezone
from unittest.mock import patch, Mock

from common.money_exchange.dolar_venezuela import USDtoVES
from users.models import SystemCurrency


@pytest.mark.django_db
@patch("common.money_exchange.dolar_venezuela.datetime")
def test_use_system_rate_if_updated(datetime_mock, system_usd):
    datetime_mock.now.return_value = datetime(
        2024, 1, 1, 22, tzinfo=timezone("America/Caracas")
    )
    system_usd.updated_at = datetime(2024, 1, 1, 12, tzinfo=timezone("America/Caracas"))
    system_usd.save()

    api_service_mock = Mock()
    api_service_mock.get_dollar_exchange_from_page.return_value = 0.0
    usd_exchange_rate_service = USDtoVES(api_service_mock)
    usd_exchange_rate = usd_exchange_rate_service.get_usd_exchange_rate()
    assert usd_exchange_rate == system_usd.ves_exchange_rate


@pytest.mark.django_db
@patch("common.money_exchange.dolar_venezuela.datetime")
def test_use_api_rate_if_system_rate_not_updated(datetime_mock, system_usd):
    datetime_mock.now.return_value = datetime(
        2024, 1, 1, 22, tzinfo=timezone("America/Caracas")
    )

    fake_exchange_rate = 150.69

    SystemCurrency.objects.filter(pk=system_usd.id).update(
        updated_at=datetime(2024, 1, 1, 8, tzinfo=timezone("America/Caracas"))
    )

    api_service_mock = Mock()
    api_service_mock.get_dollar_exchange_from_page.return_value = fake_exchange_rate
    usd_exchange_rate_service = USDtoVES(api_service_mock)
    usd_exchange_rate = usd_exchange_rate_service.get_usd_exchange_rate()
    assert usd_exchange_rate == Decimal(str(fake_exchange_rate))


@pytest.mark.django_db
@patch("common.money_exchange.dolar_venezuela.datetime")
def test_fetch_api_rate_if_prev_fetch_before_9_am(datetime_mock, system_usd):
    datetime_mock.now.return_value = datetime(
        2024, 1, 1, 22, tzinfo=timezone("America/Caracas")
    )

    fake_exchange_rate = 150.69

    SystemCurrency.objects.filter(pk=system_usd.id).update(
        updated_at=datetime(2024, 1, 1, 8, tzinfo=timezone("America/Caracas"))
    )

    api_service_mock = Mock()
    api_service_mock.get_dollar_exchange_from_page.return_value = fake_exchange_rate
    usd_exchange_rate_service = USDtoVES(api_service_mock)
    usd_exchange_rate = usd_exchange_rate_service.get_usd_exchange_rate()
    assert api_service_mock.get_dollar_exchange_from_page.call_count == 1
    assert usd_exchange_rate == Decimal(str(fake_exchange_rate))


@pytest.mark.django_db
@patch("common.money_exchange.dolar_venezuela.datetime")
def test_reuse_api_rate_if_prev_fetch_after_9_am(datetime_mock, system_usd):
    datetime_mock.now.return_value = datetime(
        2024, 1, 1, 22, tzinfo=timezone("America/Caracas")
    )

    fake_exchange_rate = 150.69

    SystemCurrency.objects.filter(pk=system_usd.id).update(
        updated_at=datetime(2024, 1, 1, 8, tzinfo=timezone("America/Caracas"))
    )

    api_service_mock = Mock()
    api_service_mock.get_dollar_exchange_from_page.return_value = fake_exchange_rate
    usd_exchange_rate_service = USDtoVES(api_service_mock)
    usd_exchange_rate_service.prev_fetch_date = datetime(
        2024, 1, 1, 10, tzinfo=timezone("America/Caracas")
    )
    usd_exchange_rate_service.api_rate = Decimal(str(120.99))
    usd_exchange_rate = usd_exchange_rate_service.get_usd_exchange_rate()
    assert api_service_mock.get_dollar_exchange_from_page.call_count == 0
    assert usd_exchange_rate == usd_exchange_rate_service.api_rate
