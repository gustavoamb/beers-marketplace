from django.core.exceptions import ValidationError
from decimal import Decimal

from rest_framework import status, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from stores.models import UserHasFavoriteStore

from locations.api.locations import (
    GeoCoordinate,
    LocationsDistance,
    SearchLocationsNearby,
)

from locations.models import Location
from locations.serializers import LocationSerializer

from common.serializers import paginate_objects


def validate_location_views_query_params(query_params):
    errors = {}
    latitude = query_params.get("latitude", None)
    if latitude is None:
        errors["latitude"] = "This query parameter is required"

    longitude = query_params.get("longitude", None)
    if longitude is None:
        errors["longitude"] = "This query parameter is required"

    if len(errors.keys()) > 0:
        raise ValidationError(errors)

    return latitude, longitude


class LocationViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = Location.objects.all()
    serializer_class = LocationSerializer


# Create your views here.
class AddressDistanceView(APIView):
    def get(self, request):
        origin = request.query_params.get("origin")
        destination = request.query_params.get("destination")
        origin_latitude, origin_longitude = origin.split(",")
        dest_latitude, dest_longitude = destination.split(",")
        origin_coordinates = (float(origin_latitude), float(origin_longitude))
        destination_coordinates = (float(dest_latitude), float(dest_longitude))

        locations = LocationsDistance()
        distance = locations.get_distance_between_locations(
            origin_coordinates, destination_coordinates
        )

        return Response(
            {"distanceInKilometers": distance},
            status=status.HTTP_200_OK,
        )


class FindStoresNearbyView(APIView):
    def get(self, request):
        query_params = request.query_params
        search_radius = query_params.get("searchRadius", 50)
        get_all_stores = query_params.get("get_all_stores", False)

        try:
            latitude, longitude = validate_location_views_query_params(query_params)
        except ValidationError as e:
            return Response(e, status=status.HTTP_400_BAD_REQUEST)

        origin = GeoCoordinate(latitude, longitude)

        searcher = SearchLocationsNearby(origin, float(search_radius), get_all_stores)
        product = query_params.get("product", None)
        store_name = query_params.get("store_name", None)
        places_nearby = searcher.find_stores_nearby(product, store_name)
        favorited_stores_ids = [
            obj["store"]
            for obj in list(
                UserHasFavoriteStore.objects.filter(user=self.request.user).values(
                    "store"
                )
            )
        ]
        for place in places_nearby:
            place["in_favorites"] = place["store"]["id"] in favorited_stores_ids

        sorted_favorited = sorted(
            [place for place in places_nearby if place["in_favorites"]],
            key=lambda x: x["distance"],
        )
        sorted_not_favorited = sorted(
            [place for place in places_nearby if not place["in_favorites"]],
            key=lambda x: x["distance"],
        )
        sorted_places = sorted_favorited + sorted_not_favorited

        page = request.query_params.get("page", 1)
        page_size = request.query_params.get("pageSize", 15)
        response = paginate_objects(sorted_places, page, page_size)

        return Response(response, status=status.HTTP_200_OK)


class FindProductsNearbyView(APIView):
    def get(self, request):
        search_radius = request.query_params.get("searchRadius", 50)
        try:
            latitude, longitude = validate_location_views_query_params(
                request.query_params
            )
        except ValidationError as e:
            return Response(e, status=status.HTTP_400_BAD_REQUEST)

        origin = GeoCoordinate(latitude, longitude)

        search_nearby = SearchLocationsNearby(origin, float(search_radius))
        products = search_nearby.find_products_nearby()
        
        sorted_products = sorted(
            products,
            key=lambda x: (Decimal(x["best_offer"]["price"]), x["best_offer"]["distance"]))

        page = request.query_params.get("page", 1)
        page_size = request.query_params.get("pageSize", 15)
        response = paginate_objects(sorted_products, page, page_size)

        return Response(response, status=status.HTTP_200_OK)


class FindProductPricesView(APIView):
    def get(self, request, product_id):
        try:
            latitude, longitude = validate_location_views_query_params(
                request.query_params
            )
        except ValidationError as e:
            return Response(e, status=status.HTTP_400_BAD_REQUEST)

        origin = GeoCoordinate(latitude, longitude)
        searcher = SearchLocationsNearby(origin, 0.0, get_all_stores=True)
        prices = searcher.find_product_prices(product_id)

        sorted_prices = sorted(
            prices,
            key=lambda x: (x["price"], x["distance"]),
        )
        page = request.query_params.get("page", 1)
        page_size = request.query_params.get("pageSize", 15)
        response = paginate_objects(sorted_prices, page, page_size)

        return Response(response, status=status.HTTP_200_OK)


class FindPromotionsNearbyView(APIView):
    def get(self, request):
        search_radius = request.query_params.get("searchRadius", 50)
        try:
            latitude, longitude = validate_location_views_query_params(
                request.query_params
            )
        except ValidationError as e:
            return Response(e, status=status.HTTP_400_BAD_REQUEST)

        origin = GeoCoordinate(latitude, longitude)
        search_nearby = SearchLocationsNearby(origin, float(search_radius))
        store_id = request.query_params.get("store_id", None)
        promotions = search_nearby.find_promotions_nearby(store_id=store_id)

        page = request.query_params.get("page", 1)
        page_size = request.query_params.get("pageSize", 15)
        response = paginate_objects(promotions, page, page_size)

        return Response(response, status=status.HTTP_200_OK)
