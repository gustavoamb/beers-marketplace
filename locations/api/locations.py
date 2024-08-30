from haversine import haversine

from django.db.models import Prefetch, Count

from stores.models import Store, Product, StoreHasProduct
from stores.serializers import (
    StoreSerializer,
    PromotionSerializer,
)

from locations.serializers import (
    ProductNearbySerializer,
    StoreNearbySerializer,
    PriceSerializer,
)


class GeoCoordinate:
    def __init__(self, latitude, longitude):
        self.latitude = float(latitude)
        self.longitude = float(longitude)


class LocationsDistance:
    def get_distance_between_locations(self, origin, destination):
        distance_in_kilometers = haversine(origin, destination)
        return distance_in_kilometers


class SearchLocationsNearby:
    def __init__(
        self, location: GeoCoordinate, radius: float, get_all_stores: bool = False
    ):
        self.origin = (location.latitude, location.longitude)
        self.search_radius_in_kilometers = radius
        self.get_all_stores = get_all_stores

    def distance_to_destination(self, destination):
        destination_coords = (destination.latitude, destination.longitude)
        return haversine(self.origin, destination_coords)

    def is_nearby(self, destination):
        if self.get_all_stores:
            return True
        distance = self.distance_to_destination(destination)
        return distance <= self.search_radius_in_kilometers

    def __find_stores_nearby(self, product_id=None, store_name=None, store_id=None):
        queryset = Store.objects.filter(verified=True).prefetch_related("location")
        if product_id is not None:
            queryset = queryset.filter(products__in=[product_id])

        if store_name is not None:
            queryset = queryset.filter(name__icontains=store_name)

        if store_id is not None:
            queryset = queryset.filter(id=store_id)

        stores = list(queryset)
        stores_nearby = [
            {"store": store, "distance": self.distance_to_destination(store.location)}
            for store in stores
            if store.location and self.is_nearby(store.location)
        ]

        return stores_nearby

    def find_stores_nearby(self, product_id=None, store_name=None):
        stores_nearby = self.__find_stores_nearby(product_id, store_name)
        for store in stores_nearby:
            store["store"] = StoreNearbySerializer(
                store["store"], context={"distance_func": self.distance_to_destination}
            ).data

        return stores_nearby

    def find_products_nearby(self):
        filter = StoreHasProduct.objects.order_by("price")
        products_with_prices = (
            Product.objects.prefetch_related(
                Prefetch("store_prices", filter, to_attr="prices"),
            )
            .annotate(Count("store_prices"))
            .filter(store_prices__count__gt=0)
        )

        serializer = ProductNearbySerializer(products_with_prices, many=True)
        products = serializer.data
        products_nearby = []
        for product in products:
            store_loc = product["best_offer"]["store"]["location"]
            destination = GeoCoordinate(store_loc["latitude"], store_loc["longitude"])
            product["best_offer"]["distance"] = self.distance_to_destination(
                destination
            )
            if self.is_nearby(destination):
                products_nearby.append(product)

        return products_nearby

    def find_product_prices(self, product_id):
        prices_qs = StoreHasProduct.objects.filter(product=product_id)
        serializer = PriceSerializer(prices_qs, many=True)
        prices = serializer.data
        for price in prices:
            store_loc = price["store"]["location"]
            destination = GeoCoordinate(store_loc["latitude"], store_loc["longitude"])
            price["distance"] = self.distance_to_destination(destination)

        return prices

    def find_promotions_nearby(self, store_id=None):
        stores_nearby = self.__find_stores_nearby(store_id=store_id)
        promotions = []

        for store in stores_nearby:
            if not store["store"].promotion_set.exists():
                continue

            store_promotions = PromotionSerializer(
                store["store"].promotion_set.all(), depth=1, many=True
            ).data
            store_data = StoreSerializer(store["store"]).data
            store_promotions = [
                {**promotion, "distance": store["distance"], "store": store_data}
                for promotion in store_promotions
            ]
            promotions += store_promotions

        return promotions
