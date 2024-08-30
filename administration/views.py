from datetime import date, datetime, timezone
from enum import Enum
from decimal import Decimal

from django.db.models import Sum, Prefetch, OuterRef, Subquery, Max, Q, F
from django.db import transaction

from rest_framework import viewsets, status, mixins
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.parsers import MultiPartParser

from administration.models import FundAccount, FundOperation
from administration.serializers import (
    FundAccountSerializer,
    FundOperationSerializer,
    AdminStoreSerializer,
    AdminStoreBalanceSerializer,
    UnclaimedPurchaseSerialiser,
    SystemCurrencySerializer,
)

from stores.api.store_balance import (
    calculate_store_balance,
    get_stores_and_unpaid_purchases,
)
from stores.models import Purchase, Store, Product
from stores.serializers import ProductSerializer

from payments.models import Movement, Funding, StorePayment, StoreFundAccount
from payments.serializers import (
    ReadOnlyMovementSerializer,
    FundingSerializer,
    StorePaymentSerializer,
    StoreFundAccountSerializer,
)
from payments.api.fulfill_orders import add_funds_to_admin_account, send_receipt_email

from users.models import SystemCurrency
from users.serializers import add_funds_to_customer

from administration.serializers import AdminStorePaymentSerializer

from common.money_exchange.dolar_venezuela import usd_exchange_rate_service
from common.utils import round_to_fixed_exponent


class TimeRanges(Enum):
    PREV_MONTH = "PREV_MONTH"
    PREV_3_MONTHS = "PREV_3_MONTHS"
    PREV_YEAR = "PREV_YEAR"


# Create your views here.
class FundAccountViewSet(viewsets.ModelViewSet):
    queryset = FundAccount.objects.all()
    serializer_class = FundAccountSerializer
    permission_classes = (IsAdminUser,)


class FundOperationViewSet(viewsets.ModelViewSet):
    queryset = FundOperation.objects.all()
    serializer_class = FundOperationSerializer
    permission_classes = (IsAdminUser,)

    def perform_create(self, serializer):
        serializer.save(admin=self.request.user)


class MovementsView(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReadOnlyMovementSerializer
    permission_classes = (IsAdminUser,)

    def get_queryset(self):
        queryset = Movement.objects.order_by("-created_at").exclude(
            movement_type=Movement.Type.GIFT_ACCEPTED
        )

        query_params = self.request.query_params
        time_range = query_params.get("time_range")
        if time_range == TimeRanges.PREV_MONTH.value:
            queryset = queryset.filter(created_at__month=date.today().month - 1)
        elif time_range == TimeRanges.PREV_3_MONTHS.value:
            curr_month = date.today().month
            last_3_months = [curr_month, curr_month - 1, curr_month - 2]
            queryset = queryset.filter(created_at__month__in=last_3_months)
        elif time_range == TimeRanges.PREV_YEAR.value:
            queryset = queryset.filter(created_at__year=date.today().year)

        start_date = query_params.get("start_date")
        end_date = query_params.get("end_date")
        if start_date is not None and end_date is not None:
            queryset = queryset.filter(created_at__date__range=(start_date, end_date))
        elif start_date is not None:
            queryset = queryset.filter(created_at__date__gte=start_date)
        elif end_date is not None:
            queryset = queryset.filter(created_at__date__lte=end_date)

        movement_type = query_params.get("movement_type", None)
        if movement_type is not None:
            queryset = queryset.filter(movement_type=movement_type)

        username = query_params.get("username")
        if username is not None:
            user_username = Q(purchase__user__username__icontains=username) | Q(
                funding__user__username__icontains=username
            )
            admin_username = Q(admin_operation__admin__username__icontains=username)
            store_username = Q(store_payment__store__user__username__icontains=username)
            username_filter = user_username | admin_username | store_username
            queryset = queryset.filter(username_filter)

        return queryset


class CommissionsTotalView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request):
        store_payments_commissions = (
            StorePayment.objects.annotate(
                purchases_commissions=Sum(
                    F("purchases__amount") * F("purchases__commission_percentage")
                )
            ).aggregate(total=Sum("purchases_commissions"))
        )["total"]
        if not store_payments_commissions:
            store_payments_commissions = Decimal(0)

        rejected = Q(status=Purchase.Status.REJECTED)
        pending = Q(status=Purchase.Status.PENDING)
        current_datetime = datetime.now(tz=timezone.utc)
        expired = pending & Q(gift_expiration_date__lte=current_datetime)
        applicable_purchases = Purchase.objects.filter(rejected | expired)
        purchases_commissions = (
            applicable_purchases.annotate(
                commission_amount=F("amount") * F("commission_percentage")
            ).aggregate(total=Sum("commission_amount"))
        )["total"]
        if not purchases_commissions:
            purchases_commissions = Decimal(0)

        total = store_payments_commissions + purchases_commissions
        usd_exchange_rate = usd_exchange_rate_service.get_usd_exchange_rate()
        total_local_currency = total * usd_exchange_rate
        return Response(
            {
                "commissions_total": total,
                "commissions_total_local_currency": total_local_currency,
            },
            status=status.HTTP_200_OK,
        )


class ForceFailedCustomerFunding(APIView):
    permission_classes = (IsAdminUser,)

    @transaction.atomic
    def patch(self, request, funding_id):
        funding = Funding.objects.get(id=funding_id)
        if funding.status != Funding.Status.FAILED:
            return Response(
                {
                    "message": "No se puede aprobar esta recarga, ya que su estado no es 'FALLIDO'"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        funding.status = Funding.Status.SUCCESSFUL
        funding.save()
        add_funds_to_customer(funding.user_id, funding.amount)
        send_receipt_email(funding.user, funding)

        amount = funding.amount
        if funding.purchased_via == Funding.PaymentPlatform.STRIPE:
            acc_name = "stripe"
        elif funding.purchased_via == Funding.PaymentPlatform.PAYPAL:
            acc_name = "paypal"
        elif funding.purchased_via == Funding.PaymentPlatform.MERCANTIL_PAGO_MOVIL:
            acc_name = "mercantil"
            amount = funding.amount_local_currency

        account = FundAccount.objects.get(name__iexact=acc_name)
        add_funds_to_admin_account(float(amount), account)

        serializer = FundingSerializer(funding)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StoresViewSet(
    viewsets.GenericViewSet, mixins.ListModelMixin, mixins.UpdateModelMixin
):
    permission_classes = (IsAdminUser,)
    serializer_class = AdminStoreSerializer

    def get_queryset(self):
        queryset = Store.objects.prefetch_related("user").all()

        query_params = self.request.query_params
        start_date = query_params.get("start_date", None)
        end_date = query_params.get("end_date", None)
        if start_date is not None and end_date is not None:
            queryset = queryset.filter(created_at__date__range=(start_date, end_date))
        elif start_date is not None:
            queryset = queryset.filter(created_at__date__gte=start_date)
        elif end_date is not None:
            queryset = queryset.filter(created_at__date__lte=end_date)

        name = query_params.get("name", None)
        if name is not None:
            queryset = queryset.filter(name__icontains=name)

        contact_name = query_params.get("contact_name", None)
        if contact_name is not None:
            queryset = queryset.filter(contact_name__icontains=contact_name)

        return queryset


class StoresBalanceView(ListAPIView):
    queryset = Store.objects.all()
    permission_classes = (IsAuthenticated, IsAdminUser)
    serializer_class = AdminStoreBalanceSerializer

    def get_queryset(self):
        queryset = self.queryset
        query_params = self.request.query_params

        store_name = query_params.get("store_name")
        if store_name is not None:
            queryset = queryset.filter(name__icontains=store_name)

        payments = (
            StorePayment.objects.filter(store=OuterRef("pk")).order_by().values("store")
        )
        last_payment = payments.annotate(last_payment=Max("created_at")).values(
            "last_payment"
        )
        queryset = queryset.annotate(last_payment_date=Subquery(last_payment))

        start_date = query_params.get("last_payment_start_date")
        end_date = query_params.get("last_payment_end_date")
        if start_date is not None and end_date is not None:
            queryset = queryset.filter(
                last_payment_date__date__range=(start_date, end_date)
            )
        elif start_date is not None:
            queryset = queryset.filter(last_payment_date__date__gte=start_date)
        elif end_date is not None:
            queryset = queryset.filter(last_payment_date__date__lte=end_date)

        return queryset

    def list(self, request):
        store_id = None
        user = request.user
        if user.is_staff:
            store_id = request.query_params.get("store", None)
        else:
            store_id = user.store.id

        balance_by_store = calculate_store_balance(
            store_id, self.get_queryset()
        ).exclude(balance=0)

        preferential_acc = StoreFundAccount.objects.filter(is_preferential=True)
        payments_qs = StorePayment.objects.order_by("-created_at")
        balance_by_store = balance_by_store.prefetch_related(
            Prefetch(
                "fund_accounts",
                queryset=preferential_acc,
                to_attr="preferential_account",
            ),
            Prefetch("payments", queryset=payments_qs),
        ).order_by("-balance")

        unpaid_balance = balance_by_store.aggregate(Sum("balance"))["balance__sum"]

        usd_exchange = usd_exchange_rate_service.get_usd_exchange_rate()
        page = self.paginate_queryset(balance_by_store)
        serializer = AdminStoreBalanceSerializer(
            page, many=True, context={"usd_ves_rate": usd_exchange}
        )
        response = self.get_paginated_response(serializer.data)
        return Response(
            {
                **response.data,
                "total": unpaid_balance,
                "usd_ves_exchange_rate": usd_exchange,
            },
            status=response.status_code,
        )


class StorePaymentViewSet(viewsets.ModelViewSet):
    parser_classes = [MultiPartParser]
    queryset = StorePayment.objects.order_by("-created_at").all()
    serializer_class = AdminStorePaymentSerializer

    def get_serializer_class(self):
        if self.action == "retrieve":
            return StorePaymentSerializer

        return super().get_serializer_class()

    def get_queryset(self):
        queryset = self.queryset

        query_params = self.request.query_params
        start_date = query_params.get("start_date", None)
        end_date = query_params.get("end_date", None)
        if start_date is not None and end_date is not None:
            queryset = queryset.filter(created_at__date__range=(start_date, end_date))
        elif start_date is not None:
            queryset = queryset.filter(created_at__date__gte=start_date)
        elif end_date is not None:
            queryset = queryset.filter(created_at__date__lte=end_date)

        store = query_params.get("store_id", None)
        if store is not None:
            queryset = queryset.filter(store=store)

        return queryset

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        data_copy = response.data.copy()
        payments = data_copy["results"]

        usd_exchange_rate = usd_exchange_rate_service.get_usd_exchange_rate()
        balance_by_store = calculate_store_balance(None)
        store_id = request.query_params.get("store_id", None)
        if store_id is not None:
            total_unpaid = balance_by_store.get(store=store_id).balance
        else:
            total_unpaid = sum([store.balance for store in balance_by_store])

        total_unpaid_bs = total_unpaid * Decimal(str(usd_exchange_rate))
        total_paid = sum([Decimal(p["amount"]) for p in payments])
        total_paid_bs = sum([p["amount_local_currency"] for p in payments])

        data_copy["total_unpaid"] = total_unpaid
        data_copy["total_unpaid_local_currency"] = total_unpaid_bs
        data_copy["total_paid"] = total_paid
        data_copy["total_paid_local_currency"] = total_paid_bs
        return Response(data_copy, status=response.status_code)

    def create(self, request, *args, **kwargs):
        store = request.data["store"]
        balances_by_store = calculate_store_balance(store)
        store_balance = balances_by_store.get(store=store)
        amount_owed = round_to_fixed_exponent(store_balance.balance)

        data = {
            "store": request.data["store"],
            "amount": amount_owed,
            "receipt": request.data["receipt"],
            "funds_account_origin": request.data["funds_account_origin"],
            "usd_exchange_rate": usd_exchange_rate_service.get_usd_exchange_rate(),
        }
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class StoreAccountsViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (IsAdminUser,)
    queryset = StoreFundAccount.objects.all()
    serializer_class = StoreFundAccountSerializer

    def get_queryset(self):
        queryset = self.queryset
        query_params = self.request.query_params
        store_id = query_params.get("store_id", None)
        if store_id is not None:
            queryset = queryset.filter(store=store_id)

        return queryset


class PendingStorePaymentView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request, store_id):
        purchases = (
            get_stores_and_unpaid_purchases(Store.objects.filter(id=store_id))
            .get(id=store_id)
            .unpaid_purchases
        )
        serializer = UnclaimedPurchaseSerialiser(purchases, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAdminUser,)
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = self.queryset
        name = self.request.query_params.get("name", None)
        if name is not None:
            queryset = queryset.filter(name__icontains=name)

        return queryset


class SystemCurrencyViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAdminUser,)
    queryset = SystemCurrency.objects.all()
    serializer_class = SystemCurrencySerializer
