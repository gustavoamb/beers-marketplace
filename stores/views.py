from datetime import datetime, timezone

from rest_framework import status, viewsets, mixins
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, UpdateAPIView
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db.models import Q

from stores import models as stores_models
from stores import serializers as stores_serializers


from common.permissions import (
    IsNaturalPersonUser,
    IsVerifiedStoreUser,
)

from users.models import User
from users.serializers import UserSerializer

from stores.api.store_balance import calculate_store_balance


# Create your views here.
class StoreViewSet(viewsets.ModelViewSet):
    serializer_class = stores_serializers.StoreSerializer
    filterset_fields = ["verified"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return stores_serializers.StoreDetailsSerializer

        return super().get_serializer_class()

    def get_queryset(self):
        queryset = stores_models.Store.objects.select_related("user", "location").all()
        store_name = self.request.query_params.get("name", None)
        if store_name is None:
            return queryset

        queryset = queryset.filter(name__startswith=store_name)
        return queryset

    @action(
        detail=False,
        methods=["get"],
        url_path="my-balance",
        permission_classes=[IsVerifiedStoreUser],
    )
    def my_balance(self, request):
        store = request.user.store
        balances_by_store = calculate_store_balance(store.id)
        store_balance = balances_by_store.get(store=store.id)
        return Response({"balance": store_balance.balance}, status=status.HTTP_200_OK)


class StoreHasProductViewSet(viewsets.ModelViewSet):
    queryset = stores_models.StoreHasProduct.objects.select_related("product").all()
    serializer_class = stores_serializers.StoreHasProductSerializer

    def get_permissions(self):
        if self.action == "list":
            return [IsAuthenticated()]

        return [IsVerifiedStoreUser()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        store = self.request.query_params.get("store_id", None)
        if store is None:
            store = self.request.user.store

        queryset = queryset.filter(store=store)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": len(serializer.data), "results": serializer.data})

    @action(
        detail=False,
        methods=["get"],
        url_path="available",
    )
    def products_available(self, request):
        store = request.user.store
        store_products = store.products.all()

        products = stores_models.Product.objects.all()
        product_name = request.query_params.get("name", None)
        if product_name is not None:
            products = products.filter(name__icontains=product_name)

        products = products.difference(store_products)

        page = self.paginate_queryset(products)
        serializer = stores_serializers.ProductSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class UserHasFavoriteStoreViewSet(
    viewsets.GenericViewSet,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
):
    queryset = stores_models.UserHasFavoriteStore.objects.all()
    serializer_class = stores_serializers.UserHasFavoriteStoreSerializer
    filterset_fields = ["user", "store"]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=["delete"], url_path="unfavorite")
    def unfavorite(self, request):
        user = request.user
        store_id = request.query_params.get("store_id")
        instance = stores_models.UserHasFavoriteStore.objects.get(
            user=user, store=store_id
        )
        instance.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductViewSet(viewsets.GenericViewSet, mixins.ListModelMixin):
    queryset = stores_models.Product.objects.all()
    serializer_class = stores_serializers.ProductSerializer
    filterset_fields = ["store"]

    def get_queryset(self):
        return super().get_queryset()


class PurchaseViewSet(viewsets.ModelViewSet):
    serializer_class = stores_serializers.PurchaseSerializer

    def get_permissions(self):
        if self.action in [
            "retrieve",
            "create",
            "partial_update",
            "reject_gift",
            "claim_gift",
        ]:
            return super().get_permissions()
        elif self.action == "information_display":
            return [AllowAny()]
        else:
            return [AllowAny()]

    def get_queryset(self):
        request = self.request

        user = request.user
        current_datetime = datetime.now(tz=timezone.utc)
        queryset = stores_models.Purchase.objects
        delivered_orderes = Q(status=stores_models.Purchase.Status.DELIVERED)
        accepted_orders = Q(status=stores_models.Purchase.Status.ACCEPTED)
        isNotExpired = ~Q(gift_expiration_date__lte=current_datetime)
        main_filter = (delivered_orderes | accepted_orders) & isNotExpired

        if user.type == User.Type.PERSON.value:
            store_id = None
        else:
            store_id = user.store.id

        from_date = request.query_params.get("from_date")
        if from_date is not None:
            from_date_utc = f"{from_date} 00:00:00+00:00"
            from_date_datetime = datetime.fromisoformat(from_date_utc)
            queryset = queryset.filter(created_at__gte=from_date_datetime)

        to_date = request.query_params.get("to_date")
        if to_date is not None:
            to_date_utc = f"{to_date} 00:00:00+00:00"
            to_date_datetime = datetime.fromisoformat(to_date_utc)
            queryset = queryset.filter(created_at__lte=to_date_datetime)

        status = request.query_params.get("status")
        if status is not None:
            status = status.upper()
            if not status == "EXPIRED":
                queryset = queryset.filter(status=status)
            else:
                pending = stores_models.Purchase.Status.PENDING.value
                accepted = stores_models.Purchase.Status.ACCEPTED.value
                queryset = queryset.filter(
                    status__in=[pending, accepted],
                    gift_expiration_date__lte=current_datetime,
                )
        reference = request.query_params.get("reference")
        if reference is not None:
            queryset = queryset.filter(reference__startswith=reference)

        if (request.method == "PATCH") | (self.kwargs.get("pk") is not None):
            return queryset
        else:
            store_purchases = Q(store=store_id)
            return queryset.filter((main_filter & store_purchases)).order_by(
                "-created_at"
            )

    @action(
        detail=True,
        methods=["get"],
        url_path="information-display",
        authentication_classes=[],
        permission_classes=[AllowAny],
    )
    def information_display(self, request, pk):
        purchase = stores_models.Purchase.objects.get(pk=pk)
        products = purchase.purchasehasproduct_set.prefetch_related(
            "product__store_prices"
        ).all()
        products = [
            {
                "name": p.product.name,
                "price": str(
                    p.product.store_prices.filter(store=purchase.store).first().price
                ),
                "quantity": p.quantity,
            }
            for p in products
        ]
        promotions = purchase.purchasehaspromotion_set.all().values(
            "promotion__title", "promotion__price", "quantity"
        )

        context = {
            "purchase_id": purchase.id,
            "purchase_reference": purchase.reference_number,
            "products": products,
            "promotions": promotions,
        }
        purchase.qr_scanned = True
        purchase.save()

        return Response(
            context,
            status=status.HTTP_200_OK,
        )

    @action(
        detail=True,
        methods=["patch"],
        url_path="reject-gift",
    )
    def reject_gift(self, request, pk):
        purchase = stores_models.Purchase.objects.get(id=pk)
        data = {"status": stores_models.Purchase.Status.REJECTED.value}
        serializer = self.get_serializer(purchase, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["patch"],
        url_path="claim-gift",
    )
    def claim_gift(self, request, pk):
        purchase = stores_models.Purchase.objects.get(id=pk)
        data = {"status": stores_models.Purchase.Status.CLAIMED.value}
        serializer = self.get_serializer(purchase, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="dispatchable")
    def dispatchable(self, request):
        status = [
            stores_models.Purchase.Status.ACCEPTED,
            stores_models.Purchase.Status.CLAIMED,
        ]
        purchases = self.get_queryset().filter(status__in=status)
        page = self.paginate_queryset(purchases)
        serializer = stores_serializers.PurchaseSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(
        detail=True,
        methods=["patch"],
        url_path="dispatch",
        authentication_classes=[],
        permission_classes=[AllowAny],
    )
    def dispatch_purchase(self, request, pk):
        dispatch_code = request.data["dispatch_code"]
        purchase = stores_models.Purchase.objects.get(id=pk)
        if dispatch_code != purchase.store.dispatch_code:
            return Response(
                {
                    "message": "El código de despacho no corresponde a la tienda de la compra"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = {"status": stores_models.Purchase.Status.DELIVERED}
        serializer = self.get_serializer(purchase, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)


class StoreReviewViewSet(viewsets.ModelViewSet):
    queryset = stores_models.StoreReview.objects.all()
    serializer_class = stores_serializers.StoreReviewSerializer
    filterset_fields = ["store", "user"]
    # TODO An user should only be able to create and edit their own reviews

    def get_permissions(self):
        users_only_actions = ["create", "partial_update"]
        if self.action in users_only_actions:
            return [IsNaturalPersonUser()]

        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        review = self.queryset.filter(user=request.user, store=request.data["store"])
        if review.exists():
            self.kwargs["pk"] = review.first().id
            return super().partial_update(request, *args, **kwargs)
        else:
            return super().create(request, *args, **kwargs)


class PromotionViewSet(viewsets.ModelViewSet):
    serializer_class = stores_serializers.PromotionSerializer

    def get_queryset(self):
        queryset = stores_models.Promotion.objects.all()
        store_id = self.request.query_params.get("store", None)
        if store_id is None:
            return queryset

        return queryset.filter(store=store_id)


class StorePromotionViewSet(viewsets.ModelViewSet):
    """Views to be used only by Stores"""

    serializer_class = stores_serializers.StorePromotionSerializer
    permission_classes = (IsVerifiedStoreUser,)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    def get_queryset(self):
        queryset = stores_models.Promotion.objects.all()
        store_id = self.request.user.store.id
        if store_id is None:
            return queryset

        return queryset.filter(store=store_id)


class ScheduleDayViews(ListAPIView, UpdateAPIView):
    serializer_class = stores_serializers.ScheduleDaySerializer

    def get_queryset(self):
        request = self.request
        user = request.user
        if user.is_staff:
            store_id = request.query_params.get("store")
        else:
            store_id = user.store.id

        queryset = stores_models.ScheduleDay.objects.all()
        if store_id is not None:
            queryset = queryset.filter(store=store_id)

        return queryset

    def patch(self, request, *args, **kwargs):
        # We're updating them in batch because the frontend
        # is going to send us the whole store's schedule.
        queryset = self.get_queryset()
        data = request.data
        serializer = self.serializer_class(queryset, data=data, partial=True, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        days_updated = serializer.data
        return Response(days_updated, status=status.HTTP_200_OK)


class GeneralSearchView(APIView):
    def get(self, request, format=None):
        name = request.query_params.get("name", None)
        if name is None:
            return Response([], status=status.HTTP_200_OK)

        users = User.objects.filter(
            is_staff=False, username__icontains=name, type=User.Type.PERSON
        )
        stores = stores_models.Store.objects.filter(name__icontains=name)
        beer_prices = stores_models.StoreHasProduct.objects.filter(
            product__name__icontains=name
        ).order_by("price")

        users_serializer = UserSerializer(
            data=users, many=True, context={"request": request}
        )
        stores_serializer = stores_serializers.StoreSerializer(data=stores, many=True)
        beers_serializer = stores_serializers.GeneralSearchStoreHasProductSerializer(
            data=beer_prices, many=True
        )
        users_serializer.is_valid()
        stores_serializer.is_valid()
        beers_serializer.is_valid()
        if len(beers_serializer.data) > 0:
            beers_serializer.data[0]["is_cheapest"] = True
        results = users_serializer.data + stores_serializer.data + beers_serializer.data

        limit = request.query_params.get("limit", None)
        if limit is not None:
            results = results[: int(limit)]

        return Response(results, status=status.HTTP_200_OK)
