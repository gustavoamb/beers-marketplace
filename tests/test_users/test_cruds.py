import pytest
from unittest.mock import patch, MagicMock

from rest_framework.test import APIClient
from rest_framework import status

from django.urls import reverse

from stores.models import Store

client = APIClient()


@pytest.mark.django_db
@patch("users.serializers.EmailMultiAlternatives")
def test_create_registration_email_sent(send_mail_mock):
    instance_mock = MagicMock()
    send_mail_mock.return_value = instance_mock
    payload = {
        "email": "test@testing.com",
        "password": "test_pwd",
        "confirm_password": "test_pwd",
        "username": "testing_user",
        "type": "PER",
        "profile": {
            "name": "I'm a testing user and this is my name!",
            "phone": "+584161234567",
        },
    }

    url = reverse("user-list")
    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    instance_mock.send.assert_called_once()


@pytest.mark.django_db
@patch("stores.serializers.generate_dispatch_code")
@patch("users.serializers.EmailMultiAlternatives")
def test_create_store_user(send_mail_mock, mock_code_generator):
    fake_dispatch_code = "12345"
    mock_code_generator.return_value = fake_dispatch_code

    payload = {
        "email": "test@testing.com",
        "password": "test_pwd",
        "confirm_password": "test_pwd",
        "username": "testing_store_user",
        "type": "STR",
        "store": {
            "name": "I'm a testing store and this is my name!",
            "phone": "+584161234567",
            "description": "Testing store description",
        },
    }
    url = reverse("user-list")
    response = client.post(url, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    store = Store.objects.get(id=response.data["store"]["id"])
    assert store.dispatch_code == fake_dispatch_code
