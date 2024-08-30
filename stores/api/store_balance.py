from datetime import datetime, timezone
from decimal import Decimal

from django.db.models import Q, F, Sum, Value, Case, When, Prefetch


from stores.models import Store, Purchase


def get_stores_and_unpaid_purchases(stores):
    delivered = Q(status=Purchase.Status.DELIVERED)
    unpaid = Q(store_payment=None)
    stores_and_unpaid_purchases = stores.prefetch_related(
        Prefetch(
            "purchase_set",
            queryset=Purchase.objects.filter(unpaid & delivered),
            to_attr="unpaid_purchases",
        )
    )
    return stores_and_unpaid_purchases


def calculate_store_balance(store_id, queryset=None):
    if queryset is None:
        queryset = Store.objects.all()

    stores = queryset.annotate(store=F("pk"))

    if store_id is not None:
        stores = stores.filter(pk=store_id)
        if not stores.exists():
            raise Exception("Store does not Exist")

    stores_and_purchases = get_stores_and_unpaid_purchases(stores)

    no_payment = Q(purchase__store_payment=None)
    delivered = Q(purchase__status=Purchase.Status.DELIVERED)

    get_delivered_sum = Sum(
        "purchase__amount",
        filter=no_payment & delivered,
    )

    delivered_sum_minus_commission = get_delivered_sum * (
        1 - F("commission_percentage")
    )
    stores_with_delivered = stores_and_purchases.annotate(
        unpaid_delivered=delivered_sum_minus_commission
    )

    stores_with_delivered = stores_with_delivered.annotate(
        unpaid_delivered=Case(
            When(unpaid_delivered=None, then=Value(Decimal(0))),
            default=F("unpaid_delivered"),
        )
    )

    balance_by_store = stores_with_delivered.annotate(balance=F("unpaid_delivered"))
    return balance_by_store
