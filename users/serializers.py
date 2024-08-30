import os
from decimal import Decimal

from django.db import transaction
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string

from rest_framework import serializers

from users.models import User, Profile, Follower

from notifications.models import Notification
from notifications.serializers import NotificationSerializer

from stores.serializers import StoreSerializer, UserCreateStoreSerializer

from common.payments.services.stripe import stripe_service
from common.utils import round_to_fixed_exponent
from common.money_exchange.dolar_venezuela import usd_exchange_rate_service

create_stripe_customer = os.getenv("STRIPE_ENABLE_CUSTOMER_CREATION").lower() == "true"


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "username",
            "name",
            "photo",
            "birthday",
            "phone",
            "description",
            "follower_count",
            "following_count",
            "is_following",
            "updated_at",
        ]

    def get_username(self, obj):
        return obj.user.username

    def get_photo(self, obj):
        if obj.user.photo is None:
            return

        try:
            return obj.user.photo.url
        except Exception:
            return

    def get_follower_count(self, obj):
        return Follower.objects.filter(user=obj.user.id).count()

    def get_following_count(self, obj):
        return Follower.objects.filter(follower=obj.user.id).count()

    def get_is_following(self, obj):
        request_user = self.context["request"].user
        return Follower.objects.filter(
            user=obj.user.id, follower=request_user.id
        ).exists()


class UserCreateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "name",
            "birthday",
            "phone",
            "description",
            "updated_at",
        ]
        read_only_fields = ["user"]


def add_funds_to_customer(customer_id, funds_quantity):
    customer = User.objects.get(pk=customer_id)
    current_balance = customer.balance
    new_balance = current_balance + round_to_fixed_exponent(str(funds_quantity))
    customer_serializer = UserSerializer(
        customer, data={"balance": new_balance}, partial=True
    )
    customer_serializer.is_valid(raise_exception=True)
    customer_serializer.save()


class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    follower_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "username",
            "name",
            "photo",
            "birthday",
            "phone",
            "description",
            "follower_count",
            "following_count",
            "is_following",
            "updated_at",
        ]

    def get_username(self, obj):
        return obj.user.username

    def get_photo(self, obj):
        if obj.user.photo is None:
            return

        try:
            return obj.user.photo.url
        except Exception:
            return

    def get_follower_count(self, obj):
        return Follower.objects.filter(user=obj.user.id).count()

    def get_following_count(self, obj):
        return Follower.objects.filter(follower=obj.user.id).count()

    def get_is_following(self, obj):
        request_user = self.context["request"].user
        return Follower.objects.filter(
            user=obj.user.id, follower=request_user.id
        ).exists()


class UserCreateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "name",
            "birthday",
            "phone",
            "description",
            "updated_at",
        ]
        read_only_fields = ["user"]


class UserSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)
    profile = UserCreateProfileSerializer(required=False)
    store = UserCreateStoreSerializer(required=False)
    is_following = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    stories_count = serializers.SerializerMethodField()
    balance_local_currency = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "confirm_password",
            "is_active",
            "type",
            "balance",
            "balance_local_currency",
            "location",
            "photo",
            "profile",
            "store",
            "created_at",
            "is_following",
            "followers_count",
            "following_count",
            "stories_count",
        ]
        read_only_fields = [
            "balance_local_currency",
            "followers_count",
            "following_count",
            "stories_count",
        ]
        extra_kwargs = {
            "password": {"write_only": True},
            "confirm_password": {"write_only": True},
        }

    def validate(self, data):
        """Validate passwords match"""
        if data.get("password") != data.get("confirm_password"):
            raise serializers.ValidationError(
                {"password_&_confirm_password": "Passwords do not match."}
            )
        # User model does not use the 'confirm_password' field.
        if "confirm_password" in data.keys():
            data.pop("confirm_password")

        # Validate complementary data was provided
        user_type = data.get("type")
        profile_data = data.get("profile", None)
        if user_type == User.Type.PERSON and profile_data is None:
            raise serializers.ValidationError(
                {
                    "profile": "This field is required when creating an user of type 'PERSON'"
                }
            )

        store_data = data.get("store", None)
        if user_type == User.Type.STORE and store_data is None:
            raise serializers.ValidationError(
                {
                    "store": "This field is required when creating an user of type 'STORE'"
                }
            )

        return data

    def create(self, validated_data):
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        password = validated_data.pop("password")
        profile_data = validated_data.pop("profile", None)
        store_data = validated_data.pop("store", None)

        with transaction.atomic():
            user = User.objects.create_user(username, email, password, **validated_data)
            user.save()

            if user.type == User.Type.PERSON:
                profile_data["user"] = user.id
                profile_serializer = ProfileSerializer(data=profile_data)
                profile_serializer.is_valid(raise_exception=True)
                profile_serializer.save()
            elif user.type == User.Type.STORE:
                store_data["user"] = user.id
                if store_data.get("location") is not None:
                    store_data["location"] = store_data["location"].id
                store_serializer = StoreSerializer(data=store_data)
                store_serializer.is_valid(raise_exception=True)
                store_serializer.save()

            # Stripe does not consider the email as an unique field,
            # so you can end up with multiple Stripe customers with the
            # same email address specially if you're just testing. Checking
            # if a Stripe customer with a certain email already exists involves
            # fetching all customers and paginating so it's not really worth it right now.
            # I'm adding this variable here to suspend Stripe customer creation if wanted,
            # be it for testing purposes or something else.
            if create_stripe_customer:
                stripe_customer_payload = {"email": email}
                stripe_customer = stripe_service.create_customer(
                    stripe_customer_payload
                )
                user.stripe_id = stripe_customer.id
                user.save()

        context = {"username": user.username}
        email_html_message = render_to_string("welcome.html", context)
        email_plaintext_message = render_to_string("welcome.txt", context)
        msg = EmailMultiAlternatives(
            subject="Bienvenido a Beers!",
            body=email_plaintext_message,
            from_email=settings.EMAIL_HOST_USER,
            to=[user.email],
        )
        msg.attach_alternative(email_html_message, "text/html")
        msg.send(fail_silently=True)

        return user

    def update(self, instance, validated_data):
        password = validated_data.get("password", None)
        if password is not None:
            instance.set_password(password)
            instance.save()
            return instance

        return super().update(instance, validated_data)

    def get_balance_local_currency(self, obj):
        usd_exchange_rate = usd_exchange_rate_service.get_usd_exchange_rate()
        return Decimal(str(obj.balance)) * usd_exchange_rate

    def get_is_following(self, obj):
        try:
            request_user = self.context["request"].user
            if not self.context["request"].method == "GET":
                return False
            return Follower.objects.filter(
                user=obj.id, follower=request_user.id
            ).exists()
        except:
            return False

    def get_followers_count(self, obj):
        return obj.followers.count()

    def get_following_count(self, obj):
        return obj.followings.count()

    def get_stories_count(self, obj):
        return obj.story_set.count()


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "created_at",
        ]
        read_only_fields = ["is_staff", "is_active"]

    def validate(self, attrs):
        attrs["is_staff"] = True
        attrs["password"] = get_random_string(15)
        return attrs

    def create(self, validated_data):
        password = validated_data["password"]
        hashed_password = make_password(password)
        validated_data["password"] = hashed_password
        admin = super().create(validated_data)

        message = (
            f"This is the password for your Beers administrator user: {password}"
        )
        send_mail(
            subject="Your Beers Administrator credentials",
            message=message,
            from_email=settings.EMAIL_HOST,
            recipient_list=[admin.email],
        )

        return admin


class FollowerSerializer(serializers.ModelSerializer):
    followed_info = serializers.SerializerMethodField()
    follower_info = serializers.SerializerMethodField()

    class Meta:
        model = Follower
        fields = [
            "id",
            "user",
            "followed_info",
            "follower",
            "follower_info",
            "follower_caught_up_with_stories",
            "created_at",
        ]

    def get_followed_info(self, obj):
        photo_url = None
        try:
            photo_url = obj.user.photo.url
        except Exception:
            pass

        try:
            obj.user.profile.name
        except Exception:
            return

        followed_attrs = {}
        try:
            followed_attrs = {
                "stories_count": obj.user.story_set.count(),
                "is_followed": obj.followed_is_followed,
                "is_follower": obj.followed_is_follower,
                "followers_count": obj.followers_count,
                "following_count": obj.following_count,
            }
        except Exception:
            pass

        info = {
            "username": obj.user.username,
            "name": obj.user.profile.name,
            "photo": photo_url,
            **followed_attrs,
        }
        return info

    def get_follower_info(self, obj):
        photo_url = None
        try:
            photo_url = obj.follower.photo.url
        except Exception:
            pass

        try:
            obj.follower.profile.name
        except Exception:
            return

        follower_attrs = {}
        try:
            follower_attrs = {
                "stories_count": obj.follower.story_set.count(),
                "is_followed": obj.follower_is_followed,
                "is_follower": obj.follower_is_follower,
                "followers_count": obj.followers_count,
                "following_count": obj.following_count,
            }
        except Exception as e:
            pass

        info = {
            "username": obj.follower.username,
            "name": obj.follower.profile.name,
            "photo": photo_url,
            **follower_attrs,
        }
        return info

    def validate_user(self, user):
        if user.type != User.Type.PERSON or user.is_staff:
            raise serializers.ValidationError(
                "Only natural person users can be followed"
            )

        return user

    def validate(self, data):
        if data["user"] == data["follower"]:
            raise serializers.ValidationError("Users cannot follow themselves")

        return data

    def create(self, validated_data):
        follower = super().create(validated_data)
        notification_data = {
            "receiver": follower.user.id,
            "type": Notification.Type.FOLLOWED,
            "follower": follower.follower.id,
        }
        notif_serializer = NotificationSerializer(data=notification_data)
        notif_serializer.is_valid(raise_exception=True)
        notif_serializer.save()

        return follower
