from django.urls import path

from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()

router.register(r"locations", views.LocationViewSet)

urlpatterns = [
    path(
        "locations/distance",
        views.AddressDistanceView.as_view(),
        name="locations_distance",
    ),
    path(
        "locations/stores-nearby",
        views.FindStoresNearbyView.as_view(),
        name="locations_stores_nearby",
    ),
    path(
        "locations/products-nearby",
        views.FindProductsNearbyView.as_view(),
        name="locations_products_nearby",
    ),
    path(
        "locations/products-nearby/<int:product_id>/",
        views.FindProductPricesView.as_view(),
        name="locations_product_prices",
    ),
    path(
        "locations/promotions-nearby",
        views.FindPromotionsNearbyView.as_view(),
        name="locations_promotions_nearby",
    ),
]

urlpatterns += router.urls
