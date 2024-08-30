from datetime import datetime, timedelta

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Prefetch

from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from stories.models import Story
from stories.serializers import (
    StorySerializer,
    UserDashboardSerializer,
    FollowingStoriesSerializer,
)

from common.utils import to_file
from common.permissions import IsNaturalPersonUser

from users.models import User


# Create your views here.
class StoryViews(ModelViewSet):
    queryset = Story.objects.all()
    serializer_class = StorySerializer

    def create(self, request, *args, **kwargs):
        request.data._mutable = True
        image = request.data["image"]
        if not isinstance(image, InMemoryUploadedFile):
            in_memory_file = to_file(image)
            request.data["image"] = in_memory_file

        return super().create(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.user.user_followers.filter(follower=request.user).update(
            follower_caught_up_with_stories=True
        )
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="following",
    )
    def following_stories(self, request):
        user = request.user

        hour_diff = timedelta(hours=12)
        today = datetime.utcnow()
        cutoff = today - hour_diff
        active_stories = Story.objects.filter(created_at__gte=cutoff).order_by(
            "-created_at"
        )

        queryset = user.user_followings.prefetch_related(
            Prefetch(
                "user__story_set",
                queryset=active_stories,
                to_attr="active_stories",
            ),
        )
        followed = [
            followed
            for followed in list(queryset)
            if len(followed.user.active_stories) > 0
        ]

        page = self.paginate_queryset(followed)
        serializer = FollowingStoriesSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class ProfileDashboard(APIView):
    permission_classes = (IsAuthenticated, IsNaturalPersonUser)

    def get(self, request, user_pk):
        user = (
            User.objects.select_related("profile")
            .prefetch_related("story_set")
            .get(pk=user_pk)
        )
        if user.type != User.Type.PERSON.value:
            return Response(
                {
                    "user": f"Cannot get profile information for non-{User.Type.PERSON.label} users"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        page = request.query_params.get("page", 1)
        serializer = UserDashboardSerializer(
            user, context={"request": request, "page": page}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
