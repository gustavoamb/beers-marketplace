from django.db.models import Q, Count, OuterRef, Exists
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import InMemoryUploadedFile

from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.generics import ListAPIView

from users.models import Profile, Follower, User
from users.serializers import (
    UserSerializer,
    AdminUserSerializer,
    ProfileSerializer,
    FollowerSerializer,
)

from common.utils import to_file


User = get_user_model()


class UsersViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    filterset_fields = ["username", "email"]

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        elif self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated()]
        else:
            return super().get_permissions()

    def get_queryset(self):
        queryset = User.objects.order_by("created_at").all()
        return queryset

    def update(self, request, *args, **kwargs):
        request.data._mutable = True
        image = request.data.get("photo")
        if image is not None and not isinstance(image, InMemoryUploadedFile):
            in_memory_file = to_file(image)
            request.data["photo"] = in_memory_file

        return super().update(request, *args, **kwargs)

    @action(
        detail=False,
        methods=["get"],
        url_path="username-email",
        permission_classes=[AllowAny],
    )
    def check_username_and_email_availability(self, request):
        username = request.query_params.get("username", None)
        email = request.query_params.get("email", None)
        users_queryset = self.get_queryset()

        is_username_available = False
        if username is not None:
            is_username_available = not users_queryset.filter(
                username=username
            ).exists()

        is_email_available = False
        if email is not None:
            is_email_available = not users_queryset.filter(email=email).exists()

        return Response(
            {
                "is_username_available": is_username_available,
                "is_email_available": is_email_available,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="me",
    )
    def currently_logged_user(self, request):
        self.queryset = User.objects.all()
        authenticated_user = request.user
        queryset = self.queryset
        serializer = self.serializer_class
        user = queryset.get(pk=authenticated_user.pk)

        user_data = serializer(user).data

        return Response(user_data, status=status.HTTP_200_OK)


class AdminUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(is_staff=True)
    serializer_class = AdminUserSerializer


class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    # TODO make sure only admins can see all profiles


class FollowerViewSet(
    viewsets.GenericViewSet,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
):
    serializer_class = FollowerSerializer
    filterset_fields = ["user"]
    # TODO
    # - Make sure an user can only see their own followers, but an,
    # admin can see any user's followers

    def get_queryset(self):
        queryset = Follower.objects.all()

        query_params = self.request.query_params

        follower_name = query_params.get("follower_name", None)
        if follower_name is not None:
            username_matches = Q(follower__username__istartswith=follower_name)
            name_matches = Q(follower__profile__name__istartswith=follower_name)
            queryset = queryset.filter(username_matches | name_matches)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        user = request.user
        is_followed = Follower.objects.filter(user=OuterRef("follower"), follower=user)
        is_follower = Follower.objects.filter(user=user, follower=OuterRef("follower"))
        queryset = queryset.annotate(
            follower_is_followed=Exists(is_followed),
            follower_is_follower=Exists(is_follower),
            followers_count=Count("follower__user_followers", distinct=True),
            following_count=Count("follower__user_followings", distinct=True),
        )

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(
        detail=False,
        methods=["delete"],
        url_path="unfollow",
    )
    def unfollow(self, request):
        follower_id = request.data["follower"]
        followed_id = request.data["followed"]
        queryset = self.get_queryset()

        follower = queryset.get(user=followed_id, follower=follower_id)
        follower.delete()

        return Response({"message": "Unfollow successful"}, status=status.HTTP_200_OK)


class FollowingView(ListAPIView):
    serializer_class = FollowerSerializer

    def get_queryset(self):
        query_params = self.request.query_params
        user = query_params.get("user")
        queryset = Follower.objects.filter(follower=user)

        following_name = query_params.get("following_name", None)
        if following_name is not None:
            username_matches = Q(user__username__istartswith=following_name)
            name_matches = Q(user__profile__name__istartswith=following_name)
            queryset = queryset.filter(username_matches | name_matches)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        user = request.user
        is_followed = Follower.objects.filter(user=OuterRef("user"), follower=user)
        is_follower = Follower.objects.filter(user=user, follower=OuterRef("user"))
        queryset = queryset.annotate(
            followed_is_followed=Exists(is_followed),
            followed_is_follower=Exists(is_follower),
            followers_count=Count("user__user_followers", distinct=True),
            following_count=Count("user__user_followings", distinct=True),
        )

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
