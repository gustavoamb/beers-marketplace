from rest_framework import serializers

from stores.models import Product, StoreHasProduct, Store
from stores.serializers import StoreSerializer, ScheduleDaySerializer

from locations.models import Location


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "latitude", "longitude"]


class ProductNearbyStoreSerializer(StoreSerializer):
    schedule_today = serializers.SerializerMethodField()
    location = LocationSerializer()

    class Meta:
        model = Store
        fields = ["id", "name", "rating", "schedule_today", "location"]
        read_only_fields = ["id", "name", "rating", "schedule_today", "location"]


class ProductNearbyPriceSerializer(serializers.ModelSerializer):
    store = ProductNearbyStoreSerializer()

    class Meta:
        model = StoreHasProduct
        fields = ["id", "price", "store"]
        read_only_fields = ["id", "price", "store"]


class PriceStoreSerializer(ProductNearbyStoreSerializer, StoreSerializer):
    schedule_today = serializers.SerializerMethodField()
    location = LocationSerializer()

    class Meta:
        model = Store
        fields = ["id", "name", "rating", "schedule_today", "location"]
        read_only_fields = [
            "id",
            "name",
            "rating",
            "schedule_today",
            "location",
        ]


class PriceSerializer(ProductNearbyPriceSerializer):
    store = PriceStoreSerializer()


class ProductNearbySerializer(serializers.ModelSerializer):
    best_offer = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "photo", "best_offer"]

    def get_best_offer(self, obj):
        return ProductNearbyPriceSerializer(obj.prices, many=True).data[0]


class StoreNearbySerializer(StoreSerializer):
    distance = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "rating",
            "reviews_count",
            "distance",
            "location_info",
            "photo",
            "schedule_today",
        ]
        read_only_fields = [
            "id",
            "name",
            "rating",
            "reviews_count",
            "distance",
            "location_info",
            "photo",
            "schedule_today",
        ]

    def get_distance(self, obj):
        calculate_distance = self.context["distance_func"]
        return calculate_distance(obj.location)
