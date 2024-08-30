from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()

router.register(r"fundings", views.FundingViewSet)
router.register(r"stores-accounts", views.StoreFundAccountViewSet)
router.register(r"stores-payments", views.StorePaymentViewSet)
router.register(r"movements", views.MovementsView, basename="movements")

urlpatterns = [
    path("stripe/checkout-session/", views.CreateStripeCheckoutSession.as_view()),
    path("stripe/webhook/", views.StripeWebhook.as_view()),
    path("stripe/setup-intents/", views.StripeSetupIntents.as_view()),
    path(
        "stripe/setup-intents/<str:setup_intent_id>/confirm",
        views.StripeSetupIntentsConfirm.as_view(),
    ),
    path("stripe/payment-methods/", views.StripePaymentMethods.as_view()),
    path(
        "stripe/payment-methods/<str:payment_method_id>/",
        views.StripePaymentMethodDetail.as_view(),
    ),
    path("recharges/stripe/", views.RechargeViaStripeView.as_view()),
    path(
        "recharges/<int:session_id>/confirm/",
        views.RechargeFundsSessionConfirmView.as_view(),
        name="stripe-confirm",
    ),
    path("paypal/checkout/", views.CreatePaypalCheckout.as_view()),
    path(
        "paypal/orders/",
        views.CreatePaypalOrderView.as_view(),
        name="paypal-create-order",
    ),
    path(
        "paypal/orders/<str:paypal_order_id>/capture/",
        views.CapturePaypalOrderView.as_view(),
        name="paypal-capture-order",
    ),
    path("orders/validate/", views.ValidateOrderView.as_view()),
    path(
        "mobile-payments/mercantil/",
        views.ConfirmMercantilMobilePaymentView.as_view(),
        name="mercantil-confirm-order",
    ),
]

urlpatterns += router.urls
