import pytest

from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from common.views import LoginView

request_factory = APIRequestFactory()


@pytest.mark.django_db
def test_natural_person_login(user):
    request = request_factory.post("beers/auth/login/")
    force_authenticate(request, user)
    view = LoginView.as_view()
    response = view(request)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_verified_store_login(store_user, store):
    store.verified = True
    store.save()
    request = request_factory.post("beers/auth/login/")
    force_authenticate(request, store_user)
    view = LoginView.as_view()
    response = view(request)

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_unverified_store_login(store_user, store):
    request = request_factory.post("beers/auth/login/")
    force_authenticate(request, store_user)
    view = LoginView.as_view()
    response = view(request)

    assert response.status_code == status.HTTP_403_FORBIDDEN
