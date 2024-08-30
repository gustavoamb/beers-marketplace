import pytest

from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import patch

from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from rest_framework import status
from rest_framework.test import APIClient

from common.utils import round_to_fixed_exponent

from stores.api.store_balance import calculate_store_balance
from stores.models import Purchase, PurchaseHasProduct
from payments.models import StorePayment
from administration.models import FundAccount


client = APIClient()


@pytest.mark.django_db
@patch("administration.views.usd_exchange_rate_service")
def test_create_payment_USD_origin(
    exchange_mock, test_image, admin_user, fund_account, store, purchase
):
    exchange_mock.get_usd_exchange_rate.return_value = Decimal(str(10.0))

    fund_account.balance = 126.00
    fund_account.save()

    store.commission_percentage = 0.20
    store.save()

    purchase.status = Purchase.Status.DELIVERED
    purchase.amount = 125.13
    purchase.save()

    amount_minus_comission = float(
        round_to_fixed_exponent(purchase.amount * (1 - store.commission_percentage))
    )

    payload = {
        "store": store.id,
        "receipt": test_image,
        "funds_account_origin": fund_account.id,
    }
    client.force_authenticate(user=admin_user)
    url = reverse("adminstorepayment-list")
    response = client.post(url, payload)
    assert response.status_code == status.HTTP_201_CREATED

    balances_by_store = calculate_store_balance(store.id)
    store_balance = balances_by_store.get(store=store.id)
    old_balance = fund_account.balance
    expected_balance = round_to_fixed_exponent(old_balance - amount_minus_comission)
    fund_account.refresh_from_db()
    assert fund_account.balance == expected_balance
    assert store_balance.balance == 0.0

    payment = StorePayment.objects.get(
        store=store, funds_account_origin=fund_account, amount=amount_minus_comission
    )


@pytest.mark.django_db
@patch("administration.views.usd_exchange_rate_service")
def test_create_payment_VES_origin(
    exchange_mock, admin_user, fund_account, store, purchase
):
    exchange_mock.get_usd_exchange_rate.return_value = Decimal(str(10.0))

    fund_account.currency = FundAccount.Currency.VES
    fund_account.balance = 1260.00
    fund_account.save()

    store.commission_percentage = 0.20
    store.save()

    purchase.status = Purchase.Status.DELIVERED
    purchase.amount = 125.13
    purchase.save()

    amount_minus_comission = float(
        round_to_fixed_exponent(purchase.amount * (1 - store.commission_percentage))
    )

    png = SimpleUploadedFile("tiny.png", b"valid_png_bin")
    payload = {
        "store": store.id,
        "receipt": png,
        "funds_account_origin": fund_account.id,
    }
    client.force_authenticate(user=admin_user)
    url = reverse("adminstorepayment-list")
    response = client.post(url, payload)
    assert response.status_code == status.HTTP_201_CREATED

    balances_by_store = calculate_store_balance(store.id)
    store_balance = balances_by_store.get(store=store.id)
    old_balance = fund_account.balance
    expected_balance = round_to_fixed_exponent(
        old_balance - amount_minus_comission * 10.0
    )
    fund_account.refresh_from_db()
    assert fund_account.balance == expected_balance
    assert store_balance.balance == 0.0

    payment = StorePayment.objects.get(
        store=store, funds_account_origin=fund_account, amount=amount_minus_comission
    )
    payment.receipt.delete()


@pytest.mark.django_db
# @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend")
@patch("payments.serializers.EmailMultiAlternatives.send")
@patch("administration.views.usd_exchange_rate_service")
def test_create_payment_email_send_to_store(
    exchange_mock,
    mail_message_send_mock,
    admin_user,
    store,
    fund_account,
    make_purchase,
    make_product,
):
    exchange_mock.get_usd_exchange_rate.return_value = Decimal(str(10.0))

    fund_account.balance = 500.0
    fund_account.save()

    product1 = make_product({"name": "Polarcita Test"})
    product2 = make_product({"name": "Solera Test"})
    product3 = make_product({"name": "Carta Roja Test"})
    product4 = make_product({"name": "Polar Light Test"})
    product5 = make_product({"name": "Ponche Crema Test"})

    purchase1 = make_purchase({"status": Purchase.Status.DELIVERED, "amount": 125.13})
    purchase2 = make_purchase({"status": Purchase.Status.DELIVERED, "amount": 84.99})
    purchase3 = make_purchase({"status": Purchase.Status.DELIVERED, "amount": 202.25})
    total = purchase1.amount + purchase2.amount + purchase3.amount

    PurchaseHasProduct.objects.create(purchase=purchase1, product=product1, quantity=3)
    PurchaseHasProduct.objects.create(purchase=purchase1, product=product2, quantity=5)
    PurchaseHasProduct.objects.create(purchase=purchase2, product=product3, quantity=2)
    PurchaseHasProduct.objects.create(purchase=purchase2, product=product1, quantity=1)
    PurchaseHasProduct.objects.create(purchase=purchase3, product=product1, quantity=4)
    PurchaseHasProduct.objects.create(purchase=purchase3, product=product2, quantity=4)
    PurchaseHasProduct.objects.create(purchase=purchase3, product=product3, quantity=4)
    PurchaseHasProduct.objects.create(purchase=purchase3, product=product4, quantity=4)
    PurchaseHasProduct.objects.create(purchase=purchase3, product=product5, quantity=4)

    store.user.email = "daniel.varela@novateva.com"
    store.user.save()

    png = SimpleUploadedFile("tiny.png", b"valid_png_bin")
    payload = {
        "store": store.id,
        "amount": total,
        "receipt": png,
        "funds_account_origin": fund_account.id,
        "usd_exchange_rate": 10.0,
    }
    client.force_authenticate(user=admin_user)
    url = reverse("adminstorepayment-list")
    response = client.post(url, payload)
    assert response.status_code == status.HTTP_201_CREATED
    mail_message_send_mock.assert_called_once()

    payment = StorePayment.objects.get(
        store=store,
        funds_account_origin=fund_account,
        amount=total,
    )
    payment.receipt.delete()


@pytest.mark.django_db
@patch("administration.views.usd_exchange_rate_service")
def test_create_payment_insufficient_funds_in_USD_origin_account(
    exchange_mock, admin_user, fund_account, store, purchase
):
    exchange_mock.get_usd_exchange_rate.return_value = Decimal(str(10.0))

    fund_account.balance = 125.12  # USD
    fund_account.save()
    purchase.status = Purchase.Status.DELIVERED
    purchase.amount = 125.13  # USD
    purchase.save()

    png = SimpleUploadedFile("tiny.png", b"valid_png_bin")
    payload = {
        "store": store.id,
        "amount": purchase.amount,
        "receipt": png,
        "funds_account_origin": fund_account.id,
        "usd_exchange_rate": 10.0,
    }
    client.force_authenticate(user=admin_user)
    url = reverse("adminstorepayment-list")
    response = client.post(url, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@patch("administration.views.usd_exchange_rate_service")
def test_create_payment_insufficient_funds_in_VES_origin_account(
    exchange_mock, admin_user, fund_account, store, purchase
):
    exchange_mock.get_usd_exchange_rate.return_value = Decimal(str(500.0))

    fund_account.currency = FundAccount.Currency.VES
    fund_account.balance = 47800  # VES
    fund_account.save()
    purchase.status = Purchase.Status.DELIVERED
    purchase.amount = 125.13  # USD
    purchase.save()

    png = SimpleUploadedFile("tiny.png", b"valid_png_bin")
    payload = {
        "store": store.id,
        "amount": purchase.amount,
        "receipt": png,
        "funds_account_origin": fund_account.id,
        "usd_exchange_rate": 500.0,
    }
    client.force_authenticate(user=admin_user)
    url = reverse("adminstorepayment-list")
    response = client.post(url, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@patch("stores.api.store_balance.datetime")
def test_created_payments_reference_numbers(
    datetime_mock, test_image, admin_user, fund_account, store, purchases_v2
):
    datetime_mock.now.return_value = datetime(2021, 12, 31, tzinfo=timezone.utc)

    fund_account.balance = 10000.0
    fund_account.save()

    client.force_authenticate(user=admin_user)
    url = reverse("adminstorepayment-list")

    first_purchases_set = purchases_v2[:5]
    first_set_total = round_to_fixed_exponent(
        sum([(purchase.amount) for purchase in first_purchases_set])
    )
    for purchase in first_purchases_set:
        purchase.status = Purchase.Status.DELIVERED

    Purchase.objects.bulk_update(first_purchases_set, ["status"])
    payload1 = {
        "store": store.id,
        "amount": first_set_total,
        "receipt": test_image,
        "funds_account_origin": fund_account.id,
        "usd_exchange_rate": 10.0,
    }
    response1 = client.post(url, payload1)
    data1 = response1.data
    assert response1.status_code == status.HTTP_201_CREATED
    assert data1["reference_number"] == "000001"

    second_purchases_set = purchases_v2[5:]
    second_set_total = round_to_fixed_exponent(
        sum([purchase.amount for purchase in second_purchases_set])
    )
    for purchase in second_purchases_set:
        purchase.status = Purchase.Status.DELIVERED

    Purchase.objects.bulk_update(second_purchases_set, ["status"])
    png2 = SimpleUploadedFile("tiny2.png", b"valid_png_bin")
    payload2 = {
        "store": store.id,
        "amount": second_set_total,
        "receipt": png2,
        "funds_account_origin": fund_account.id,
        "usd_exchange_rate": 10.0,
    }
    response2 = client.post(url, payload2)
    data2 = response2.data
    assert response2.status_code == status.HTTP_201_CREATED
    assert data2["reference_number"] == "000002"

    payment1 = StorePayment.objects.get(pk=data1["id"])
    payment2 = StorePayment.objects.get(pk=data2["id"])
    payment1.receipt.delete()
    payment2.receipt.delete()
