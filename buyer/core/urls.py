from django.urls import path, include
from rest_framework.routers import DefaultRouter

from core.views import (
    BuyerProfileViewSet,
    OrderRequestViewSet,
    DealViewSet,
    PaymentViewSet,
    ShipmentViewSet,
    DisputeViewSet,
    RatingViewSet,
)
from core.payment_webhook import PaymentWebhookView

app_name = 'core'

router = DefaultRouter()
router.register(r'buyers', BuyerProfileViewSet, basename='buyer-profile')
router.register(r'orders', OrderRequestViewSet, basename='order-request')
router.register(r'deals', DealViewSet, basename='deal')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'shipments', ShipmentViewSet, basename='shipment')
router.register(r'disputes', DisputeViewSet, basename='dispute')
router.register(r'ratings', RatingViewSet, basename='rating')

urlpatterns = [
    path('', include(router.urls)),
    path('webhooks/payment/', PaymentWebhookView.as_view(), name='payment-webhook'),
]
