import pytest

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from payments.models import StoreFundAccount

client = APIClient()


@pytest.fixture
def make_store_fund_account(store):
    def __make_store_account(data=None):
        if data is None:
            data = {"store": store, "type": StoreFundAccount.Type.VES}

        return StoreFundAccount.objects.create(**data)

    return __make_store_account


@pytest.mark.django_db
def test_create_VES_account(store):
    store.verified = True
    store.save()

    client.force_authenticate(user=store.user)
    url = reverse("storefundaccount-list")
    payload = {
        "type": StoreFundAccount.Type.VES,
        "number": "123456789",
        "holder_name": "Place Holder",
        "bank_name": "Bank of Testing",
        "doc_type": "CI",
        "doc_number": "987654321",
    }
    response = client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_USD_account(store, make_store_fund_account):
    store.verified = True
    store.save()
    make_store_fund_account()
    client.force_authenticate(user=store.user)
    url = reverse("storefundaccount-list")
    payload = {
        "type": StoreFundAccount.Type.USD,
        "number": "123456789",
        "holder_name": "Place Holder",
        "bank_name": "Bank of Testing",
    }
    response = client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_MOBILE_PAY_account(store, make_store_fund_account):
    store.verified = True
    store.save()
    make_store_fund_account()
    client.force_authenticate(user=store.user)
    url = reverse("storefundaccount-list")
    payload = {
        "type": StoreFundAccount.Type.MOBILE_PAY,
        "phone": "+584241234567",
        "bank_name": "Bank of Testing",
        "doc_type": "RIF",
        "doc_number": "946873521",
    }
    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_PAYPAL_account(store, make_store_fund_account):
    store.verified = True
    store.save()
    make_store_fund_account()
    client.force_authenticate(user=store.user)
    url = reverse("storefundaccount-list")
    payload = {"type": StoreFundAccount.Type.PAYPAL, "holder_name": "paypalaccount"}
    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_non_VES_account_without_prev_VES_account(store):
    store.verified = True
    store.save()
    client.force_authenticate(user=store.user)
    url = reverse("storefundaccount-list")
    payload = {
        "type": StoreFundAccount.Type.USD,
        "number": "123456789",
        "holder_name": "Place Holder",
        "bank_name": "Bank of Testing",
    }
    response = client.post(url, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["type"]
        == "At least one (1) VES account must exist before creating other account types"
    )


@pytest.mark.django_db
def test_create_another_preferential_account(store, make_store_fund_account):
    store.verified = True
    store.save()
    prev_account = make_store_fund_account()
    prev_account.is_preferential = True
    prev_account.save()

    client.force_authenticate(user=store.user)
    url = reverse("storefundaccount-list")
    payload = {
        "type": StoreFundAccount.Type.USD,
        "number": "123456789",
        "holder_name": "Place Holder",
        "bank_name": "Bank of Testing",
        "is_preferential": True,
    }
    response = client.post(url, payload, format="json")
    data = response.data
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        data["is_preferential"]
        == "An Store can only have one (1) account set as preferential"
    )


@pytest.mark.django_db
def test_update_account_to_preferential_with_prev_preferential(
    store, make_store_fund_account
):
    store.verified = True
    store.save()
    prev_account = make_store_fund_account()
    prev_account.is_preferential = True
    prev_account.save()

    account = make_store_fund_account()

    client.force_authenticate(user=store.user)
    url = reverse("storefundaccount-detail", kwargs={"pk": account.id})
    payload = {
        "type": StoreFundAccount.Type.USD,
        "number": "123456789",
        "holder_name": "Place Holder",
        "bank_name": "Bank of Testing",
        "is_preferential": True,
    }
    response = client.patch(url, payload, format="json")
    data = response.data
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        data["is_preferential"]
        == "An Store can only have one (1) account set as preferential"
    )


@pytest.mark.django_db
def test_delete_last_VES_account(store, make_store_fund_account):
    store.verified = True
    store.save()
    account = make_store_fund_account()
    client.force_authenticate(user=store.user)
    url = reverse("storefundaccount-detail", kwargs={"pk": account.id})
    response = client.delete(url, format="json")
    data = response.data
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        data["message"]
        == "Could not delete the specified account because it's the last VES account remaining"
    )
