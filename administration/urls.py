from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()

router.register(r"funds/accounts", views.FundAccountViewSet)
router.register(r"funds/operations", views.FundOperationViewSet)
router.register(r"movements", views.MovementsView, basename="admin-movements")
router.register(
    r"store-payments", views.StorePaymentViewSet, basename="adminstorepayment"
)
router.register(r"products", views.ProductViewSet)
router.register(r"currencies", views.SystemCurrencyViewSet)
router.register(r"stores", views.StoresViewSet, basename="admin-stores")
router.register(r"stores-fund-accounts", views.StoreAccountsViewSet)

urlpatterns = [
    path("commissions/", views.CommissionsTotalView.as_view()),
    path(
        "customer-fundings/force/<int:funding_id>/",
        views.ForceFailedCustomerFunding.as_view(),
        name="admin-force-funding",
    ),
    # path("stores/", views.StoresViewSet.as_view(), name="admin-stores-list"),
    path(
        "stores/balance/",
        views.StoresBalanceView.as_view(),
        name="admin-stores-balance",
    ),
    path(
        "store-payments/pending/<int:store_id>/",
        views.PendingStorePaymentView.as_view(),
        name="admin-stores-payments-pending",
    ),
]

urlpatterns += router.urls
