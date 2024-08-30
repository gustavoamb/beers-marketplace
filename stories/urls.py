from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()

router.register(r"stories", views.StoryViews)

urlpatterns = [
    path(
        r"users/<int:user_pk>/profile/",
        views.ProfileDashboard.as_view(),
        name="profile-dashboard",
    ),
]

urlpatterns += router.urls
