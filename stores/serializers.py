import os
import pytz
import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch
from django.conf import settings
from django.core.mail import send_mail

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
from firebase_admin.messaging import Message, Notification as FCMNotification
from fcm_django.models import FCMDevice

from common.serializers import (
    DynamicFieldsModelSerializer,
    DynamicDepthModelSerializer,
    UpdateListSerializer,
)

from stores.models import (
    Product,
    StoreHasProduct,
    Store,
    ScheduleDay,
    Purchase,
    PurchaseHasProduct,
    PurchaseHasPromotion,
    UserHasFavoriteStore,
    Promotion,
    StoreReview,
    get_gift_expiration_date,
    generate_dispatch_code,
)

from notifications.models import Notification, PUSH_NOTIFICATION_LABEL
from notifications.serializers import NotificationSerializer

logger = logging.getLogger("stores_serializers")
logger.setLevel(os.getenv("LOG_LEVEL", logging.INFO))


class ProductSerializer(DynamicDepthModelSerializer, DynamicFieldsModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "description", "photo", "created_at"]


class ScheduleDaySerializer(DynamicFieldsModelSerializer):
    class Meta:
        model = ScheduleDay
        fields = ["id", "store", "day", "open_hour", "close_hour", "closed"]
        list_serializer_class = UpdateListSerializer


class StoreSerializer(DynamicFieldsModelSerializer):
    schedule_today = serializers.SerializerMethodField()
    location_info = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            "id",
            "user",
            "name",
            "description",
            "doc_type",
            "doc_number",
            "location",
            "location_info",
            "rating",
            "reviews_count",
            "phone",
            "verified",
            "schedule_today",
            "created_at",
            "updated_at",
            "photo",
            "contact_name",
            "contact_job",
            "contact_phone",
            "dispatch_code",
        ]
        read_only_fields = ["dispatch_code"]

    def get_photo(self, obj):
        if obj.user.photo is None:
            return

        try:
            return obj.user.photo.url
        except Exception:
            return

    def get_schedule_today(self, obj):
        if not obj.schedule_today:
            return

        schedule_today = ScheduleDaySerializer(
            obj.schedule_today, fields=("day", "open_hour", "close_hour", "closed")
        )

        open_hour = (
            datetime.now()
            .astimezone(pytz.timezone("America/Caracas"))
            .replace(
                hour=int(schedule_today.data["open_hour"].split(":")[0]),
                minute=int(schedule_today.data["open_hour"].split(":")[1]),
            )
        )
        close_hour = (
            datetime.now()
            .astimezone(pytz.timezone("America/Caracas"))
            .replace(
                hour=int(schedule_today.data["close_hour"].split(":")[0]),
                minute=int(schedule_today.data["close_hour"].split(":")[1]),
            )
        )

        if close_hour < open_hour:
            close_hour = close_hour + timedelta(days=1)

        is_closed = not (
            open_hour
            <= datetime.now().astimezone(pytz.timezone("America/Caracas"))
            <= close_hour
        )

        return {
            **schedule_today.data,
            "closed": is_closed or schedule_today.data["closed"],
        }

    def get_location_info(self, obj):
        location_info = {
            "latitude": obj.location.latitude,
            "longitude": obj.location.longitude,
        }
        return location_info

    def validate(self, data):
        if self.instance:
            # Update
            return data

        data["dispatch_code"] = generate_dispatch_code()
        return data

    def create(self, validated_data):
        with transaction.atomic():
            store = super().create(validated_data)
            schedule_data = [{"store": store.id, "day": i} for i in range(7)]
            schedule_serializer = ScheduleDaySerializer(data=schedule_data, many=True)
            schedule_serializer.is_valid(raise_exception=True)
            schedule_serializer.save()

        return store

    def update(self, instance, validated_data):
        verified = validated_data.get("verified", None)
        if verified:
            message = (
                "Congratulations, your Beers store has been verified by our staff."
            )
            send_mail(
                subject="Your Beers store has been verified",
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[instance.user.email],
            )

        return super().update(instance, validated_data)


class StoreNearbySerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["id", "name"]
        read_only_fields = ["id", "name"]


class StoreDetailsSerializer(serializers.ModelSerializer):
    scheduleday_set = ScheduleDaySerializer(
        many=True, fields=["day", "open_hour", "close_hour", "closed"]
    )
    email = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "phone",
            "email",
            "description",
            "doc_type",
            "doc_number",
            "commission_percentage",
            "contact_name",
            "contact_phone",
            "contact_job",
            "photo",
            "location",
            "scheduleday_set",
            "dispatch_code",
        ]
        read_only_fields = fields
        depth = 1

    def get_email(self, obj):
        return obj.user.email

    def get_location(self, obj):
        loc = obj.location
        return {"id": loc.id, "latitude": loc.latitude, "Longitude": loc.longitude}

    def get_photo(self, obj):
        if obj.user.photo is None:
            return

        try:
            return obj.user.photo.url
        except Exception:
            return


class StoreHasProductSerializer(serializers.ModelSerializer):
    store = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        default=serializers.CurrentUserDefault(),
    )
    product_info = serializers.SerializerMethodField()

    def validate_store(self, store_user):
        return store_user.store

    class Meta:
        model = StoreHasProduct
        fields = ["id", "store", "product", "product_info", "price"]
        validators = [
            UniqueTogetherValidator(
                queryset=StoreHasProduct.objects.all(),
                fields=("store", "product"),
            )
        ]
        read_only_fields = ["product_info"]

    def get_product_info(self, obj):
        photo_url = obj.product.photo.url if obj.product.photo else None
        return {
            "name": obj.product.name,
            "photo": photo_url,
            "created_at": obj.product.created_at,
        }


class GeneralSearchStoreHasProductSerializer(serializers.ModelSerializer):
    store = StoreSerializer(fields=["id", "name"])
    product = ProductSerializer(fields=["id", "name", "photo"])

    class Meta:
        model = StoreHasProduct
        fields = ["id", "store", "product", "price"]
        read_only_fields = ["id", "store", "product", "price"]


class UserHasFavoriteStoreSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()
    store_info = serializers.SerializerMethodField()

    class Meta:
        model = UserHasFavoriteStore
        fields = ["id", "user", "user_info", "store", "store_info"]
        read_only_fields = ["user"]

    def get_user_info(self, obj):
        from users.serializers import UserSerializer

        user_serializer = UserSerializer(obj.user)
        return user_serializer.data

    def get_store_info(self, obj):
        store_serializer = StoreSerializer(obj.store)
        return store_serializer.data


class UserCreateStoreSerializer(StoreSerializer):
    class Meta:
        model = Store
        fields = [
            "id",
            "user",
            "name",
            "description",
            "doc_type",
            "doc_number",
            "location",
            "phone",
            "verified",
            "created_at",
            "updated_at",
            "contact_name",
            "contact_job",
            "contact_phone",
        ]
        read_only_fields = ["user"]


class PromotionSerializer(DynamicDepthModelSerializer):
    class Meta:
        model = Promotion
        fields = [
            "id",
            "title",
            "description",
            "photo",
            "price",
            "created_at",
            "updated_at",
        ]


class StorePromotionSerializer(serializers.ModelSerializer):
    store = serializers.PrimaryKeyRelatedField(
        queryset=Store.objects.all(),
        default=serializers.CurrentUserDefault(),
    )

    class Meta:
        model = Promotion
        fields = [
            "id",
            "store",
            "title",
            "description",
            "photo",
            "price",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["store"]

    def validate_store(self, store_user):
        return store_user.store


class PurchaseHasProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseHasProduct
        fields = ["id", "purchase", "product", "quantity", "created_at", "updated_at"]


class PurchaseHasPromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseHasPromotion
        fields = ["id", "purchase", "promotion", "quantity", "created_at", "updated_at"]


class PurchaseNotificationHelper:
    def __init__(self, purchase, products, promotions):
        self.purchase = purchase
        self.products = products
        self.promotions = promotions

    def __create_notification(self, data):
        notif_serializer = NotificationSerializer(data=data)
        notif_serializer.is_valid(raise_exception=True)
        notification = notif_serializer.save()

        try:
            device = FCMDevice.objects.filter(user=notification.receiver).last()
            device.send_message(
                Message(
                    notification=FCMNotification(
                        title=PUSH_NOTIFICATION_LABEL[data["type"]]
                    ),
                    data={"title": PUSH_NOTIFICATION_LABEL[data["type"]]},
                )
            )
        except Exception as e:
            logger.error(f"Error sending Purchase notifications: {str(e)}")

    def create_store_purchase_notification(self):
        # WARNING: This method is deprecated or not implemented and should be either removed or integrated properly.
        notification_data = {
            "receiver": self.purchase.store.user.id,
            "type": Notification.Type.STORE_PURCHASE,
            "purchase": self.purchase.id,
        }
        self.__create_notification(notification_data)

    def create_user_purchase_notification(self):
        # WARNING: This method is deprecated or not implemented and should be either removed or integrated properly.
        notification_data = {
            "receiver": self.purchase.user.id,
            "type": Notification.Type.USER_PURCHASE,
            "purchase": self.purchase.id,
        }
        self.__create_notification(notification_data)

    def create_gift_notification(self):
        if self.products:
            notification_data = {
                "receiver": self.purchase.gift_recipient.id,
                "type": Notification.Type.GIFT_RECEIVED,
                "purchase": self.purchase.id,
            }
            self.__create_notification(notification_data)

        if self.promotions:
            notification_data = {
                "receiver": self.purchase.gift_recipient.id,
                "type": Notification.Type.GIFT_RECEIVED,
                "purchase": self.purchase.id,
            }
            self.__create_notification(notification_data)

    def create_gift_sender_notification(self, gift):
        if gift.status == Purchase.Status.ACCEPTED:
            notification_data = {
                "receiver": self.purchase.user.id,
                "type": Notification.Type.GIFT_ACCEPTED,
                "purchase": self.purchase.id,
            }
        if gift.status == Purchase.Status.PENDING:
            notification_data = {
                "receiver": self.purchase.user.id,
                "type": Notification.Type.GIFT_RECEIVED,
                "purchase": self.purchase.id,
            }
        if gift.status == Purchase.Status.REJECTED:
            notification_data = {
                "receiver": self.purchase.user.id,
                "type": Notification.Type.GIFT_REJECTED,
                "purchase": self.purchase.id,
            }

        self.__create_notification(notification_data)


class PurchaseSerializerHelper:
    def __init__(self, purchase, serializer_validated_data, products, promotions):
        self.purchase = purchase
        self.validated_data = serializer_validated_data
        self.products = products
        self.promotions = promotions

    def associate_products_with_purchase(self):
        table_data = [
            {
                "purchase": self.purchase.id,
                "product": product["product_id"],
                "quantity": product["quantity"],
            }
            for product in self.products
        ]
        table_serializer = PurchaseHasProductSerializer(data=table_data, many=True)
        table_serializer.is_valid(raise_exception=True)
        table_serializer.save()

    def associate_promotions_with_purchase(self):
        table_data = [
            {
                "purchase": self.purchase.id,
                "promotion": promotion["id"],
                "quantity": promotion["quantity"],
            }
            for promotion in self.promotions
        ]
        table_serializer = PurchaseHasPromotionSerializer(data=table_data, many=True)
        table_serializer.is_valid(raise_exception=True)
        table_serializer.save()

    def __create_gift_movements(self, movement_types):
        from payments.models import Movement
        from payments.serializers import MovementSerializer

        grouping_id = Movement.objects.get_next_grouping_id()
        movements_data = [
            {
                "movement_type": mov_type,
                "purchase": self.purchase.id,
                "grouping_id": grouping_id,
            }
            for mov_type in movement_types
        ]
        movement_serializer = MovementSerializer(data=movements_data, many=True)
        movement_serializer.is_valid(raise_exception=True)
        movement_serializer.save()

    def create_initial_movements(self):
        from payments.models import Movement

        movement_types = [
            Movement.Type.GIFT_SENT.value,
            Movement.Type.GIFT_RECEIVED.value,
        ]
        self.__create_gift_movements(movement_types)

    def create_gift_movements(self, status, expire=False):
        from payments.models import Movement

        status_enum = Purchase.Status
        movement_types = None
        if status == status_enum.DELIVERED.value:
            movement_types = [
                Movement.Type.GIFT_CLAIMED.value,
                Movement.Type.BAR_CLAIM_PAYMENT.value,
            ]
        elif status == status_enum.REJECTED.value:
            movement_types = [
                Movement.Type.GIFT_REFUNDED.value,
            ]
            current_datetime = datetime.now(tz=timezone.utc)
            has_expired = current_datetime > self.purchase.gift_expiration_date
            if has_expired and expire:
                movement_types.append(Movement.Type.GIFT_EXPIRED.value)
            else:
                movement_types.append(Movement.Type.GIFT_REJECTED.value)
        elif status == status_enum.ACCEPTED.value:
            movement_types = [Movement.Type.GIFT_ACCEPTED.value]

        if movement_types is None:
            return

        self.__create_gift_movements(movement_types)


class PurchaseProductSerializer(DynamicFieldsModelSerializer):
    price = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "photo", "price", "quantity"]
        read_only_fields = ["id", "name", "photo", "price", "quantity"]

    def get_price(self, obj):
        if not obj.price:
            return

        return obj.price[0].price

    def get_quantity(self, obj):
        if not obj.price:
            return

        return obj.detail[0].quantity


class PurchaseSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()
    store_info = serializers.SerializerMethodField()
    days_before_gift_expiration = serializers.SerializerMethodField()
    gift_recipient_info = serializers.SerializerMethodField()
    movement_type = serializers.SerializerMethodField()
    products_purchased = serializers.JSONField(write_only=True)
    promotions_purchased = serializers.JSONField(write_only=True)
    products = serializers.SerializerMethodField()
    products_quantity = serializers.IntegerField(read_only=True)
    promotions = serializers.SerializerMethodField()
    refund_info = serializers.SerializerMethodField()

    class Meta:
        model = Purchase
        fields = [
            "id",
            "user",
            "user_info",
            "status",
            "store",
            "store_info",
            "amount",
            "commission_percentage",
            "commission_amount",
            "refund_info",
            "reference",
            "reference_number",
            "qr_scanned",
            "gift_recipient",
            "gift_recipient_info",
            "gift_has_expired",
            "gift_expiration_date",
            "days_before_gift_expiration",
            "store_payment",
            "products_purchased",
            "products",
            "products_quantity",
            "promotions_purchased",
            "promotions",
            "movement_type",
            "message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "store",
            "commission_percentage",
            "commission_amount",
            "reference",
            "reference_number",
            "products",
            "promotions",
            "qr_scanned",
        ]

    def get_user_info(self, obj):
        from users.serializers import UserSerializer

        user_serializer = UserSerializer(obj.user)
        return user_serializer.data

    def get_store_info(self, obj):
        store_name = obj.store.name
        store_location = obj.store.location
        latitude = 0
        longitude = 0
        if store_location:
            latitude = store_location.latitude
            longitude = store_location.longitude
        return {"name": store_name, "latitude": latitude, "longitude": longitude}

    def get_days_before_gift_expiration(self, obj):
        seconds_in_a_day = 86400
        return round(obj.seconds_before_gift_expiration / seconds_in_a_day)

    def get_gift_recipient_info(self, obj):
        from users.serializers import UserSerializer

        if obj.gift_recipient is None:
            return

        try:
            obj.gift_recipient.profile
        except Exception:
            return

        user_serializer = UserSerializer(obj.gift_recipient)
        return user_serializer.data

    def get_movement_type(self, obj):
        return "purchase"

    def get_products(self, obj: Purchase):
        store_price = StoreHasProduct.objects.filter(store=obj.store)
        purchase_has_product = PurchaseHasProduct.objects.filter(purchase=obj.id)
        products = obj.products.prefetch_related(
            Prefetch("store_prices", queryset=store_price, to_attr="price"),
            Prefetch(
                "purchasehasproduct_set",
                queryset=purchase_has_product,
                to_attr="detail",
            ),
        )
        serializer = PurchaseProductSerializer(products, many=True)
        return serializer.data

    def get_promotions(self, obj: Purchase):
        promotions = obj.purchasehaspromotion_set.all().values(
            "promotion__id", "promotion__title", "promotion__price", "quantity"
        )
        return promotions

    def get_refund_info(self, obj):
        gift_rejected_status = Purchase.Status.REJECTED.value
        if obj.status == gift_rejected_status or obj.gift_has_expired:
            refund_fee = obj.amount * Decimal(0.15)
            return {"amount": obj.amount - refund_fee, "fee": refund_fee}

    def validate_status(self, new_status):
        if not self.instance:
            return new_status

        # We're updating a purchase
        if (
            self.instance.status != Purchase.Status.ACCEPTED
            and new_status == Purchase.Status.DELIVERED
        ):
            raise serializers.ValidationError(
                f"Cannot assign status 'DELIVERED', current status must be 'CLAIMED', current status: {self.instance.status}"
            )

        return new_status

    def validate(self, data):
        gift_recipient = data.get("gift_recipient", None)
        if gift_recipient:
            data["gift_expiration_date"] = get_gift_expiration_date()

        if self.instance:
            # We're updating a purchase
            return data

        promotions = data.get("promotions_purchased", None)
        products = data.get("products_purchased", None)
        if not promotions and not products:
            raise serializers.ValidationError(
                "A purchase must contain at least one (1) promotion or product"
            )

        # Validate again that the user can afford the purchase
        user = data["user"]
        amount = data["amount"]
        if user.balance < amount:
            raise serializers.ValidationError(
                "The user's current balance is insuficient to complete the purchase"
            )

        if products:
            any_product_price_id = products[0]["price_id"]
            data["store"] = StoreHasProduct.objects.get(pk=any_product_price_id).store

        # An order can only possess promotions from the same store
        if promotions:
            any_promotion_id = promotions[0]["id"]
            data["store"] = Promotion.objects.get(pk=any_promotion_id).store

        data["commission_percentage"] = data["store"].commission_percentage
        return data

    def validate_products_purchased(self, products):
        products_ids = [product["price_id"] for product in products]
        products_in_db = StoreHasProduct.objects.filter(pk__in=products_ids)
        if products_in_db.count() != len(products_ids):
            raise serializers.ValidationError(
                "Could not find one or more of the order's products prices"
            )

        for product in products:
            product["product_id"] = StoreHasProduct.objects.get(
                pk=product["price_id"]
            ).product_id

        return products

    def validate_promotions_purchased(self, promotions):
        promotion_ids = [promotion["id"] for promotion in promotions]
        promotions_in_db = Promotion.objects.filter(pk__in=promotion_ids)
        if promotions_in_db.count() != len(promotion_ids):
            raise serializers.ValidationError(
                "Could not find one or more of the order's promotions"
            )

        return promotions

    def create(self, validated_data):
        with transaction.atomic():
            products = validated_data.pop("products_purchased")
            promotions = validated_data.pop("promotions_purchased")

            # TODO remove notification logic from this method
            # this should only handle Purchase creation logic
            purchase = super().create(validated_data)
            helper_methods = PurchaseSerializerHelper(
                purchase, validated_data, products, promotions
            )
            helper_methods.create_initial_movements()
            if products:
                helper_methods.associate_products_with_purchase()

            if promotions:
                helper_methods.associate_promotions_with_purchase()

            user = validated_data["user"]
            user.balance -= purchase.amount
            user.save()

        try:
            notifications_helper = PurchaseNotificationHelper(
                purchase, products, promotions
            )
            if purchase.gift_recipient is not None:
                notifications_helper.create_gift_notification()
        except Exception as e:
            logger.error(f"Error creating Purchase notifications: {str(e)}")

        return purchase

    def update(self, instance, validated_data):
        from users.serializers import add_funds_to_customer

        with transaction.atomic():
            status_enum = Purchase.Status
            status = validated_data.get("status")
            if status == "GIFT_EXPIRED":
                validated_data["status"] = status_enum.REJECTED.value

            purchase_updated = super().update(instance, validated_data)

            helper_methods = PurchaseSerializerHelper(
                purchase_updated, validated_data, None, None
            )
            helper_methods.create_gift_movements(
                status, self.context.get("expire", False)
            )

            if purchase_updated.status == status_enum.REJECTED.value:
                comission = purchase_updated.amount * Decimal(0.15)
                amount_refunded = purchase_updated.amount - comission
                add_funds_to_customer(purchase_updated.user.id, amount_refunded)

            try:
                notifications_helper = PurchaseNotificationHelper(
                    purchase_updated, None, None
                )
                notifications_helper.create_gift_sender_notification(purchase_updated)
            except Exception as e:
                logger.error(f"Error creating Gift notifications: {str(e)}")

        return purchase_updated


class StoreReviewSerializer(serializers.ModelSerializer):
    user_info = serializers.SerializerMethodField()

    class Meta:
        model = StoreReview
        fields = [
            "id",
            "user",
            "user_info",
            "store",
            "content",
            "rating",
            "created_at",
            "updated_at",
        ]

    def get_user_info(self, obj):
        user_info = {"name": obj.user.profile.name, "photo": None}

        if obj.user.photo is None:
            return user_info

        try:
            user_info["photo"] = obj.user.photo.url
        except Exception:
            return user_info

        return user_info
