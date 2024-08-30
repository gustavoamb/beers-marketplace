from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()

router.register(r"users", views.UsersViewSet, basename="user")
router.register(r"admins", views.AdminUserViewSet, basename="admin")
router.register(r"profiles", views.ProfileViewSet)
router.register(r"followers", views.FollowerViewSet, basename="follower")

urlpatterns = [
    path("following/", views.FollowingView.as_view()),
]

urlpatterns += router.urls
