from rest_framework import serializers

from stores.models import Purchase

from notifications.models import Notification


class NotificationUpdateListSerializer(serializers.ListSerializer):
    def update(self, instances, validated_data):
        instance_hash = {index: instance for index, instance in enumerate(instances)}

        result = [
            self.child.update(instance_hash[index], attrs)
            for index, attrs in enumerate(validated_data)
        ]

        return result


class NotificationSerializer(serializers.ModelSerializer):
    follower_info = serializers.SerializerMethodField()
    gift_info = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "receiver",
            "type",
            "read",
            "follower",
            "follower_info",
            "purchase",
            "gift_info",
            "created_at",
        ]
        list_serializer_class = NotificationUpdateListSerializer

    def get_follower_info(self, obj):
        if obj.follower is None:
            return

        follower_photo_url = None
        try:
            follower_photo_url = obj.follower.photo.url
        except Exception:
            pass
        return {
            "id": obj.follower.id,
            "name": obj.follower.profile.name,
            "username": obj.follower.username,
            "photo": follower_photo_url,
        }

    def get_gift_info(self, obj):
        if obj.purchase is None:
            return

        purchase = obj.purchase
        sender_photo_url = None
        try:
            sender_photo_url = purchase.user.photo.url
        except Exception:
            pass
        info = {
            "purchase_id": purchase.id,
            "gift_sender": {
                "id": purchase.user.id,
                "username": purchase.user.username,
                "name":  purchase.user.profile.name,
                "photo":  sender_photo_url
            },
            "store_name": purchase.store.name,
            "days_before_gift_expiration": round(purchase.seconds_before_gift_expiration / 86400),
            "gift_status": Purchase.Status(purchase.status).label,
            "products_quantity": purchase.products_quantity,
            "promotions_quantity": purchase.promotions_quantity,
        }
        return info
