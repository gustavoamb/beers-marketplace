from django.urls import path

from rest_framework.routers import DefaultRouter

from fcm_django.api.rest_framework import FCMDeviceAuthorizedViewSet

from . import views

router = DefaultRouter()

router.register("devices", FCMDeviceAuthorizedViewSet)

urlpatterns = [
    path("notifications/", views.NotificationListView.as_view()),
    path("notifications/mark-as-read/", views.NotificationMarkAllAsReadView.as_view()),
]

urlpatterns += router.urls
