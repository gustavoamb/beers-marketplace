import pytest

from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from notifications.models import Notification
from notifications.views import NotificationMarkAllAsReadView


request_factory = APIRequestFactory()


@pytest.fixture
def unread_notifications(user):
    data = [
        Notification(receiver=user, type=Notification.Type.GIFT_ACCEPTED),
        Notification(receiver=user, type=Notification.Type.GIFT_RECEIVED),
        Notification(receiver=user, type=Notification.Type.FOLLOWED),
    ]
    notification = Notification.objects.bulk_create(data)
    return notification


def test_mark_all_notifications_as_read(user, unread_notifications):
    request = request_factory.patch("beers/notifications/mark-as-read/")
    force_authenticate(request, user)
    view = NotificationMarkAllAsReadView.as_view()
    response = view(request)
    data = response.data

    assert response.status_code == status.HTTP_200_OK
    assert len(data) == 3
    assert all([notif["read"] for notif in data])
