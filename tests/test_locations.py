import pytest

from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from locations.models import Location

client = APIClient()


@pytest.fixture
def make_location():
    def __make_location(data):
        return Location.objects.create(**data)

    return __make_location


@pytest.mark.django_db
def test_stores_near_user(user, make_user, make_store, make_location):
    store_user1 = make_user()
    store1 = make_store({"user": store_user1})
    loc_within_range = make_location({"latitude": 10.150811, "longitude": -64.633939})
    store1.location = loc_within_range
    store1.verified = True
    store1.save()

    store_user2 = make_user()
    store2 = make_store({"user": store_user2})
    loc_outside_range = make_location({"latitude": 12.150811, "longitude": -68.633939})
    store2.location = loc_outside_range
    store2.verified = True
    store2.save()

    origin_location = make_location({"latitude": 10.151725, "longitude": -64.634667})
    client.force_authenticate(user=user)
    url = reverse("locations_stores_nearby")
    radius = 50
    latitude = origin_location.latitude
    longitude = origin_location.longitude
    query_string = f"?searchRadius={radius}&latitude={latitude}&longitude={longitude}"
    response = client.get(url + query_string, format="json")
    data = response.data

    assert response.status_code == status.HTTP_200_OK
    assert data["count"] == 1
    assert data["results"][0]["store"]["id"] == store1.id


@pytest.mark.django_db
def test_stores_with_product_near_user(
    user, make_user, make_store, make_product, make_location, relate_product_to_store
):
    product = make_product()

    store_user1 = make_user()
    store1 = make_store({"user": store_user1})
    loc_within_range = make_location({"latitude": 10.150811, "longitude": -64.633939})
    store1.location = loc_within_range
    store1.verified = True
    store1.save()

    store_user2 = make_user()
    store2 = make_store({"user": store_user2})
    store2.location = loc_within_range
    store2.verified = True
    store2.save()
    relate_product_to_store(product, store2)

    origin_location = make_location({"latitude": 10.151725, "longitude": -64.634667})
    client.force_authenticate(user=user)
    url = reverse("locations_stores_nearby")
    radius = 50
    latitude = origin_location.latitude
    longitude = origin_location.longitude
    query_string = f"?searchRadius={radius}&latitude={latitude}&longitude={longitude}&product={product.id}"
    response = client.get(url + query_string, format="json")
    data = response.data

    assert response.status_code == status.HTTP_200_OK
    assert data["count"] == 1
    assert data["results"][0]["store"]["id"] == store2.id


@pytest.mark.django_db
def test_products_near_user(
    user, store, make_product, make_location, relate_product_to_store
):
    products = [make_product() for i in range(4)]

    dest_location = make_location({"latitude": 10.150811, "longitude": -64.633939})
    store.location = dest_location
    store.verified = True
    store.save()

    for product in products:
        relate_product_to_store(product, store)

    origin_location = make_location({"latitude": 10.151725, "longitude": -64.634667})

    client.force_authenticate(user=user)
    url = reverse("locations_products_nearby")
    radius = 50
    latitude = origin_location.latitude
    longitude = origin_location.longitude
    query_string = f"?searchRadius={radius}&latitude={latitude}&longitude={longitude}"
    response = client.get(url + query_string, format="json")
    data = response.data

    assert response.status_code == status.HTTP_200_OK
    assert len(data) == 4


@pytest.mark.django_db
def test_promotions_near_user(user, store, make_promotion, make_location):
    promos = [make_promotion() for i in range(5)]

    dest_location = make_location({"latitude": 10.150811, "longitude": -64.633939})
    store.location = dest_location
    store.verified = True
    store.save()

    origin_location = make_location({"latitude": 10.151725, "longitude": -64.634667})

    client.force_authenticate(user=user)
    url = reverse("locations_promotions_nearby")
    radius = 50
    latitude = origin_location.latitude
    longitude = origin_location.longitude
    query_string = f"?searchRadius={radius}&latitude={latitude}&longitude={longitude}"
    response = client.get(url + query_string, format="json")
    data = response.data

    assert response.status_code == status.HTTP_200_OK
    assert data["count"] == 5
