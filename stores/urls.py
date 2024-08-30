from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()

router.register(r"stores", views.StoreViewSet, basename="store")
router.register(r"stores-products", views.StoreHasProductViewSet)
router.register(
    r"stores-promotions", views.StorePromotionViewSet, basename="store-products"
)
router.register(r"purchases", views.PurchaseViewSet, basename="purchase")
router.register(r"stores-reviews", views.StoreReviewViewSet)
router.register(r"promotions", views.PromotionViewSet, basename="promotion")
router.register(r"user-favorite-stores", views.UserHasFavoriteStoreViewSet)

urlpatterns = [
    path("schedules/", views.ScheduleDayViews.as_view()),
    path("schedules/<int:pk>/", views.ScheduleDayViews.as_view()),
]

urlpatterns += router.urls
