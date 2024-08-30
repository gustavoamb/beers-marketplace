from django.db import transaction

from rest_framework import serializers

from stories.models import Story

from users.models import User, Profile, Follower
from users.serializers import ProfileSerializer

from common.serializers import paginate_objects


class StorySerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_photo = serializers.SerializerMethodField()
    user_username = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    stories_count = serializers.SerializerMethodField()

    class Meta:
        model = Story
        fields = [
            "id",
            "user",
            "user_name",
            "user_photo",
            "image",
            "user_username",
            "followers_count",
            "following_count",
            "stories_count",
        ]
        read_only_fields = ["followers_count", "following_count", "stories_count"]

    def get_user_name(self, obj):
        return obj.user.profile.name

    def get_user_username(self, obj):
        return obj.user.username

    def get_user_photo(self, obj):
        try:
            return obj.user.photo.url
        except Exception:
            return

    def get_followers_count(self, obj):
        return obj.user.user_followers.count()

    def get_following_count(self, obj):
        return obj.user.user_followings.count()

    def get_stories_count(self, obj):
        return obj.user.story_set.count()

    def create(self, validated_data):
        with transaction.atomic():
            story = super().create(validated_data)
            story.user.user_followers.update(follower_caught_up_with_stories=False)

        return story


class FollowingStoriesSerializer(serializers.ModelSerializer):
    active_stories = serializers.SerializerMethodField()

    class Meta:
        model = Follower
        fields = [
            "id",
            "user",
            "follower",
            "follower_caught_up_with_stories",
            "active_stories",
        ]
        read_only_fields = [
            "id",
            "user",
            "follower",
            "follower_caught_up_with_stories",
            "active_stories",
        ]

    def get_active_stories(self, obj):
        serializer = StorySerializer(obj.user.active_stories, many=True)
        return serializer.data


class ProfileDashboardSerializer(ProfileSerializer):
    class Meta:
        model = Profile
        fields = [
            "username",
            "name",
            "photo",
            "follower_count",
            "following_count",
            "is_following",
        ]


class StoryDashboardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Story
        fields = ["id", "image"]


class UserDashboardSerializer(serializers.ModelSerializer):
    profile = ProfileDashboardSerializer()
    stories_quantity = serializers.SerializerMethodField()
    stories = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "profile", "stories_quantity", "stories"]

    def get_stories_quantity(self, obj):
        return obj.story_set.count()

    def get_stories(self, obj):
        stories = obj.story_set.all()
        page = self.context.get("page", 1)
        pagination = paginate_objects(stories, int(page), 15)

        serializer = StoryDashboardSerializer(stories, many=True)
        pagination["results"] = serializer.data

        return pagination
