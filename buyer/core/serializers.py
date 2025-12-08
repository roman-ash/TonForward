"""
Serializers for core models.
"""

from decimal import Decimal
from typing import Dict, Any

from rest_framework import serializers
from django.conf import settings

from core.models import (
    BuyerProfile,
    OrderRequest,
    Deal,
    OnchainDeal,
    Payment,
    Shipment,
    Dispute,
    Rating,
)


class BuyerProfileSerializer(serializers.ModelSerializer):
    """Сериализатор для профиля байера."""

    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = BuyerProfile
        fields = [
            'id', 'user', 'user_full_name', 'user_email',
            'ton_address', 'bio', 'country', 'city',
            'rating', 'deals_completed',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'rating', 'deals_completed', 'created_at', 'updated_at']


class BuyerProfileCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания профиля байера."""

    class Meta:
        model = BuyerProfile
        fields = ['ton_address', 'bio', 'country', 'city']


class OrderRequestCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания заявки заказчиком."""

    class Meta:
        model = OrderRequest
        fields = [
            'id', 'title', 'description', 'store_link',
            'store_city', 'store_country',
            'max_item_price_rub', 'buyer_fee_rub',
            'service_fee_rub', 'insurance_rub',
            'status', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'created_at']

    def create(self, validated_data: Dict[str, Any]) -> OrderRequest:
        """Создает заявку от текущего пользователя."""
        user = self.context['request'].user
        return OrderRequest.objects.create(customer=user, **validated_data)


class OrderRequestSerializer(serializers.ModelSerializer):
    """Сериализатор для заявки заказчика."""

    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    total_amount_rub = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderRequest
        fields = [
            'id', 'customer', 'customer_name',
            'title', 'description', 'store_link',
            'store_city', 'store_country',
            'max_item_price_rub', 'buyer_fee_rub',
            'service_fee_rub', 'insurance_rub',
            'total_amount_rub', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'customer', 'created_at', 'updated_at']


class OrderBidSerializer(serializers.Serializer):
    """Сериализатор для отклика байера на заявку."""

    message = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация отклика."""
        request = self.context['request']
        order = self.context['order']

        # Проверяем, что пользователь - байер
        if not hasattr(request.user, 'buyer_profile'):
            raise serializers.ValidationError({
                'error': 'Только байеры могут откликаться на заявки.'
            })

        # Проверяем, что заявка открыта
        if order.status != OrderRequest.Status.OPEN:
            raise serializers.ValidationError({
                'error': f'Заявка уже не в статусе OPEN. Текущий статус: {order.status}'
            })

        # Проверяем, что заказчик не откликается на свою заявку
        if order.customer == request.user:
            raise serializers.ValidationError({
                'error': 'Нельзя откликнуться на свою заявку.'
            })

        return attrs


class DealSerializer(serializers.ModelSerializer):
    """Сериализатор для сделки."""

    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    buyer_name = serializers.CharField(source='buyer.user.get_full_name', read_only=True)
    order_title = serializers.CharField(source='order.title', read_only=True)
    total_amount_ton = serializers.DecimalField(max_digits=18, decimal_places=9, read_only=True)

    class Meta:
        model = Deal
        fields = [
            'id', 'order', 'order_title',
            'customer', 'customer_name',
            'buyer', 'buyer_name',
            'item_price_max_rub', 'buyer_fee_rub',
            'service_fee_rub', 'insurance_rub',
            'item_price_ton', 'buyer_fee_ton',
            'service_fee_ton', 'insurance_ton',
            'total_amount_ton', 'status',
            'purchase_deadline', 'ship_deadline', 'confirm_deadline',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order', 'customer', 'buyer',
            'created_at', 'updated_at'
        ]


class PaymentSerializer(serializers.ModelSerializer):
    """Сериализатор для платежа."""

    deal_id = serializers.IntegerField(source='deal.id', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'deal', 'deal_id',
            'provider', 'provider_payment_id',
            'amount_rub', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'deal', 'provider_payment_id',
            'status', 'created_at', 'updated_at'
        ]


class PaymentCreateSerializer(serializers.Serializer):
    """Сериализатор для создания платежа."""

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация платежа."""
        deal = self.context['deal']
        request = self.context['request']

        # Проверяем, что заказчик создает платеж
        if deal.customer != request.user:
            raise serializers.ValidationError({
                'error': 'Только заказчик может создавать платеж для сделки.'
            })

        # Проверяем статус сделки - платеж можно создать только для новой сделки
        if deal.status != Deal.Status.NEW:
            raise serializers.ValidationError({
                'error': f'Платеж можно создать только для сделки со статусом NEW. Текущий статус: {deal.status}'
            })

        # Проверяем, что платеж еще не создан
        if hasattr(deal, 'payment'):
            raise serializers.ValidationError({
                'error': 'Платеж для этой сделки уже существует.'
            })

        return attrs


class ShipmentSerializer(serializers.ModelSerializer):
    """Сериализатор для отправки."""

    deal_id = serializers.IntegerField(source='deal.id', read_only=True)

    class Meta:
        model = Shipment
        fields = [
            'id', 'deal', 'deal_id',
            'tracking_number', 'shipping_provider',
            'receipt_photo_url', 'shipped_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class DisputeSerializer(serializers.ModelSerializer):
    """Сериализатор для спора."""

    deal_id = serializers.IntegerField(source='deal.id', read_only=True)
    opened_by_name = serializers.CharField(source='opened_by.get_full_name', read_only=True)
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True)

    class Meta:
        model = Dispute
        fields = [
            'id', 'deal', 'deal_id',
            'opened_by', 'opened_by_name',
            'reason_code', 'description',
            'resolution', 'resolved_by', 'resolved_by_name',
            'resolved_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'deal', 'opened_by',
            'resolved_by', 'resolved_at',
            'created_at', 'updated_at'
        ]


class DisputeCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания спора."""

    class Meta:
        model = Dispute
        fields = ['reason_code', 'description']

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация создания спора."""
        deal = self.context['deal']
        request = self.context['request']

        # Проверяем, что пользователь - участник сделки
        if deal.customer != request.user and deal.buyer.user != request.user:
            raise serializers.ValidationError({
                'error': 'Только участники сделки могут открыть спор.'
            })

        # Проверяем статус сделки - спор можно открыть для активных статусов
        valid_statuses = [
            Deal.Status.NEW,
            Deal.Status.FUNDED,
            Deal.Status.PURCHASED,
            Deal.Status.SHIPPED
        ]
        if deal.status not in valid_statuses:
            raise serializers.ValidationError({
                'error': f'Спор можно открыть только для сделок со статусами: {", ".join(valid_statuses)}'
            })

        # Проверяем, что спор еще не открыт
        if hasattr(deal, 'dispute'):
            raise serializers.ValidationError({
                'error': 'Спор для этой сделки уже открыт.'
            })

        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Dispute:
        """Создает спор от текущего пользователя."""
        deal = self.context['deal']
        user = self.context['request'].user

        return Dispute.objects.create(
            deal=deal,
            opened_by=user,
            **validated_data
        )


class RatingSerializer(serializers.ModelSerializer):
    """Сериализатор для рейтинга."""

    deal_id = serializers.IntegerField(source='deal.id', read_only=True)
    rated_by_name = serializers.CharField(source='rated_by.get_full_name', read_only=True)
    rated_user_name = serializers.CharField(source='rated_user.get_full_name', read_only=True)

    class Meta:
        model = Rating
        fields = [
            'id', 'deal', 'deal_id',
            'rated_by', 'rated_by_name',
            'rated_user', 'rated_user_name',
            'score', 'comment',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'deal', 'rated_by',
            'rated_user', 'created_at', 'updated_at'
        ]


class RatingCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания рейтинга."""

    class Meta:
        model = Rating
        fields = ['score', 'comment']

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация создания рейтинга."""
        deal = self.context['deal']
        request = self.context['request']

        # Проверяем, что сделка завершена
        if deal.status != Deal.Status.COMPLETED:
            raise serializers.ValidationError({
                'error': 'Рейтинг можно оставить только для завершенных сделок.'
            })

        # Проверяем, что пользователь - участник сделки
        if deal.customer != request.user and deal.buyer.user != request.user:
            raise serializers.ValidationError({
                'error': 'Только участники сделки могут оставить рейтинг.'
            })

        # Определяем, кого оцениваем (противоположную сторону)
        if deal.customer == request.user:
            rated_user = deal.buyer.user
        else:
            rated_user = deal.customer

        # Проверяем, что рейтинг еще не оставлен
        if Rating.objects.filter(deal=deal, rated_by=request.user).exists():
            raise serializers.ValidationError({
                'error': 'Вы уже оставили рейтинг для этой сделки.'
            })

        attrs['rated_user'] = rated_user
        return attrs

    def create(self, validated_data: Dict[str, Any]) -> Rating:
        """Создает рейтинг от текущего пользователя."""
        deal = self.context['deal']
        user = self.context['request'].user

        return Rating.objects.create(
            deal=deal,
            rated_by=user,
            **validated_data
        )
