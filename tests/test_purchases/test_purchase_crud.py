import pytest

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from stores.models import Purchase, PurchaseHasProduct
from stores.serializers import PurchaseSerializer

client = APIClient()


@pytest.mark.django_db
def test_create_purchase_and_pivot_table_entries(
    user, user2, products, store, relate_product_to_store
):
    user.balance = 40.0
    user.save()

    price1 = relate_product_to_store(products[0], store)
    price2 = relate_product_to_store(products[1], store)
    request_data = {
        "user": user.id,
        "amount": 38.5,
        "gift_recipient": user2.id,
        "products_purchased": [
            {
                "price_id": str(price1.id),
                "quantity": 3,
            },
            {
                "price_id": str(price2.id),
                "quantity": 1,
            },
        ],
        "promotions_purchased": [],
    }
    serializer = PurchaseSerializer(data=request_data)
    serializer.is_valid(raise_exception=True)
    purchase = serializer.save()

    assert Purchase.objects.count() == 1
    assert PurchaseHasProduct.objects.count() == 2
    assert purchase.purchasehasproduct_set.count() == 2


@pytest.mark.django_db
def test_update_to_delivered(store, purchase):
    store.verified = True
    store.save()

    purchase.status = Purchase.Status.CLAIMED
    purchase.save()

    client.force_authenticate(user=store.user)
    url = reverse("purchase-detail", kwargs={"pk": purchase.id})
    payload = {"status": Purchase.Status.DELIVERED.value}
    response = client.patch(url, payload, format="json")
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_update_to_delivered_invalid_prev_status(store, purchase):
    store.verified = True
    store.save()

    client.force_authenticate(user=store.user)
    url = reverse("purchase-detail", kwargs={"pk": purchase.id})
    payload = {"status": Purchase.Status.DELIVERED.value}
    response = client.patch(url, payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        response.data["status"][0]
        == "Cannot assign status 'DELIVERED', current status must be 'CLAIMED', current status: PENDING"
    )
