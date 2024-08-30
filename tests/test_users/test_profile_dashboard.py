import pytest

from rest_framework.test import APIClient
from rest_framework import status

from django.urls import reverse


@pytest.mark.django_db
def test_no_followers_or_following(user_with_profile):
    client = APIClient()
    client.force_authenticate(user=user_with_profile)
    url = reverse("profile-dashboard", kwargs={"user_pk": user_with_profile.id})
    response = client.get(url)
    data = response.data

    assert response.status_code == status.HTTP_200_OK
    assert data["profile"]["follower_count"] == 0
    assert data["profile"]["following_count"] == 0


@pytest.mark.django_db
def test_followers_following_counts(user_with_profile, followers, following):
    client = APIClient()
    client.force_authenticate(user=user_with_profile)
    url = reverse("profile-dashboard", kwargs={"user_pk": user_with_profile.id})
    response = client.get(url)
    data = response.data

    assert response.status_code == status.HTTP_200_OK
    assert data["profile"]["follower_count"] == len(followers)
    assert data["profile"]["following_count"] == len(following)
