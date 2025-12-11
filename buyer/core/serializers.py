"""
Serializers for core models.
"""

from decimal import Decimal
from typing import Dict, Any

from rest_framework import serializers
from django.conf import settings

from core.models import (
    BuyerProfile,
    OfficialStoreDomain,
    OrderRequest,
    Deal,
    OnchainDeal,
    Payment,
    Shipment,
    Dispute,
    Rating,
    PurchaseConfirmation,
    ShippingAddress,
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
    
    # Фильтруем description от контактов
    description = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = OrderRequest
        fields = [
            'id', 'title', 'description',
            'item_store_url', 'item_category',  # Новые обязательные поля
            'shipping_weight_category',  # Категория веса для доставки
            'allow_personal_handover', 'allow_delivery_by_mail',  # Разрешенные форматы доставки
            'country_from', 'country_to',  # Страны
            'store_link', 'store_city', 'store_country',  # Старые поля (deprecated)
            'max_item_price_rub', 'buyer_fee_rub',
            'service_fee_rub', 'insurance_rub',
            'status', 'store_verified', 'created_at'
        ]
        read_only_fields = ['id', 'status', 'store_verified', 'created_at']

    def validate_item_store_url(self, value: str) -> str:
        """Валидация URL магазина и проверка по whitelist."""
        from core.store_validation import extract_domain, validate_store_domain
        
        domain = extract_domain(value)
        is_allowed, status, reason = validate_store_domain(domain)
        
        if not is_allowed:
            if status == 'REJECTED':
                raise serializers.ValidationError(
                    f"Магазин {domain} в черном списке. {reason}"
                )
            else:
                # Магазин не найден - требует проверки
                raise serializers.ValidationError(
                    f"Магазин {domain} не найден в списке разрешенных. "
                    f"Заявка будет отправлена на модерацию."
                )
        
        return value

    def validate_description(self, value: str) -> str:
        """Фильтруем контактные данные из описания."""
        if value:
            from core.contact_filter import validate_text_no_contacts
            validate_text_no_contacts(value)
        return value

    def create(self, validated_data: Dict[str, Any]) -> OrderRequest:
        """Создает заявку от текущего пользователя с валидацией магазина."""
        from core.store_validation import extract_domain, validate_store_domain
        
        user = self.context['request'].user
        
        # Извлекаем и валидируем домен
        item_store_url = validated_data.get('item_store_url')
        if item_store_url:
            domain = extract_domain(item_store_url)
            is_allowed, status, _ = validate_store_domain(domain)
            
            validated_data['item_store_domain'] = domain
            validated_data['store_verified'] = (status == 'VERIFIED')
        else:
            # Если item_store_url не указан, используем старый store_link
            store_link = validated_data.get('store_link', '')
            if store_link:
                domain = extract_domain(store_link)
                is_allowed, status, _ = validate_store_domain(domain)
                validated_data['item_store_url'] = store_link
                validated_data['item_store_domain'] = domain
                validated_data['store_verified'] = (status == 'VERIFIED')
        
        # Если category не указана, используем OTHER
        if 'item_category' not in validated_data:
            validated_data['item_category'] = OrderRequest.ItemCategory.OTHER
        
        return OrderRequest.objects.create(customer=user, **validated_data)


class OrderRequestSerializer(serializers.ModelSerializer):
    """Сериализатор для заявки заказчика."""

    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    total_amount_rub = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    description = serializers.SerializerMethodField()

    class Meta:
        model = OrderRequest
        fields = [
            'id', 'customer', 'customer_name',
            'title', 'description',
            'item_store_url', 'item_store_domain', 'store_verified', 'item_category',
            'store_link', 'store_city', 'store_country',  # Старые поля (deprecated)
            'max_item_price_rub', 'buyer_fee_rub',
            'service_fee_rub', 'insurance_rub',
            'total_amount_rub', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'customer', 'item_store_domain', 'store_verified', 'created_at', 'updated_at']
    
    def get_description(self, obj: OrderRequest) -> str:
        """Фильтруем контакты из описания при выводе."""
        if obj.description:
            from core.contact_filter import filter_contacts
            return filter_contacts(obj.description)
        return obj.description or ''


class OrderRequestForBuyerSerializer(serializers.ModelSerializer):
    """Сериализатор заявки для байера (без адреса доставки)."""
    
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    total_amount_rub = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    description = serializers.SerializerMethodField()

    class Meta:
        model = OrderRequest
        fields = [
            'id', 'title', 'description',
            'item_store_url', 'item_store_domain', 'store_verified', 'item_category',
            'store_city', 'store_country',  # Город/страна магазина (НЕ адрес доставки!)
            'max_item_price_rub', 'buyer_fee_rub',
            'service_fee_rub', 'insurance_rub',
            'total_amount_rub', 'status',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_description(self, obj: OrderRequest) -> str:
        """Фильтруем контакты из описания."""
        if obj.description:
            from core.contact_filter import filter_contacts
            return filter_contacts(obj.description)
        return obj.description or ''


class OrderBidSerializer(serializers.Serializer):
    """Сериализатор для отклика байера на заявку."""

    message = serializers.CharField(required=False, allow_blank=True, max_length=500)
    delivery_mode = serializers.ChoiceField(
        choices=Deal.DeliveryMode.choices,
        required=True,
        help_text='Режим доставки, который предлагает байер'
    )
    
    def validate_message(self, value: str) -> str:
        """Фильтруем контактные данные из сообщения."""
        if value:
            from core.contact_filter import validate_text_no_contacts
            validate_text_no_contacts(value)
        return value

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
        
        # Проверяем совместимость режима доставки с предпочтениями заказчика
        delivery_mode = attrs.get('delivery_mode')
        if delivery_mode == Deal.DeliveryMode.PERSONAL_HANDOVER:
            if not order.allow_personal_handover:
                raise serializers.ValidationError({
                    'delivery_mode': 'Заказчик не разрешил личную передачу товара для этой заявки.'
                })
        elif delivery_mode in [Deal.DeliveryMode.INTERNATIONAL_MAIL, Deal.DeliveryMode.DOMESTIC_MAIL]:
            if not order.allow_delivery_by_mail:
                raise serializers.ValidationError({
                    'delivery_mode': 'Заказчик не разрешил доставку почтой для этой заявки.'
                })

        return attrs


class DealSerializer(serializers.ModelSerializer):
    """Сериализатор для сделки (для заказчика и админа)."""

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
            'item_store_url', 'item_store_domain', 'store_verified',
            # Финансовые поля
            'item_price_max_rub', 'actual_item_price_rub',
            'buyer_reward_rub', 'buyer_fee_rub',  # buyer_fee_rub для обратной совместимости
            'service_fee_rub', 'insurance_rub',
            'shipping_budget_rub', 'actual_shipping_cost_rub',
            'total_reserved_amount_rub',
            # Доставка
            'delivery_mode', 'shipping_weight_category',
            'country_from', 'country_to',
            # TON
            'item_price_ton', 'buyer_fee_ton',
            'shipping_budget_ton',
            'service_fee_ton', 'insurance_ton',
            'total_amount_ton',
            # Статус и дедлайны
            'status',
            'purchase_deadline', 'ship_deadline', 'confirm_deadline',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order', 'customer', 'buyer',
            'item_store_domain', 'store_verified',
            'shipping_budget_rub', 'total_reserved_amount_rub',
            'created_at', 'updated_at'
        ]


class DealForBuyerSerializer(serializers.ModelSerializer):
    """Сериализатор для сделки для байера (без адреса до PURCHASED)."""

    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    order_title = serializers.CharField(source='order.title', read_only=True)
    total_amount_ton = serializers.DecimalField(max_digits=18, decimal_places=9, read_only=True)
    
    # Адрес НЕ включается до статуса PURCHASED

    class Meta:
        model = Deal
        fields = [
            'id', 'order', 'order_title',
            'customer_name',  # Только имя, не полная информация
            'item_store_url', 'item_store_domain', 'store_verified',
            'item_price_max_rub', 'actual_item_price_rub', 'buyer_fee_rub',
            'service_fee_rub', 'insurance_rub',
            'shipping_budget_rub', 'actual_shipping_cost_rub',
            'item_price_ton', 'buyer_fee_ton',
            'shipping_budget_ton',
            'service_fee_ton', 'insurance_ton',
            'total_amount_ton', 'status',
            'purchase_deadline', 'ship_deadline', 'confirm_deadline',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order', 'item_store_domain', 'store_verified',
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
    actual_shipping_cost_rub = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text='Фактическая стоимость доставки по чеку'
    )

    class Meta:
        model = Shipment
        fields = [
            'id', 'deal', 'deal_id',
            'tracking_number', 'shipping_provider',
            'receipt_photo_url', 'shipped_at',
            'actual_shipping_cost_rub',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_actual_shipping_cost_rub(self, value: Decimal) -> Decimal:
        """Проверяем, что стоимость доставки не превышает бюджет."""
        if value is not None:
            deal = self.context.get('deal')
            if deal and hasattr(deal, 'shipping_budget_rub') and deal.shipping_budget_rub:
                if value > deal.shipping_budget_rub:
                    raise serializers.ValidationError(
                        f"Фактическая стоимость доставки ({value}) не может превышать "
                        f"бюджет доставки ({deal.shipping_budget_rub})"
                    )
        return value


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
    
    def validate_description(self, value: str) -> str:
        """Фильтруем контактные данные из описания спора."""
        if value:
            from core.contact_filter import validate_text_no_contacts
            validate_text_no_contacts(value)
        return value

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

    def validate_comment(self, value: str) -> str:
        """Фильтруем контактные данные из комментария к рейтингу."""
        if value:
            from core.contact_filter import validate_text_no_contacts
            validate_text_no_contacts(value)
        return value

    def create(self, validated_data: Dict[str, Any]) -> Rating:
        """Создает рейтинг от текущего пользователя."""
        deal = self.context['deal']
        user = self.context['request'].user

        return Rating.objects.create(
            deal=deal,
            rated_by=user,
            **validated_data
        )


class PurchaseConfirmationSerializer(serializers.ModelSerializer):
    """Сериализатор для подтверждения покупки."""

    deal_id = serializers.IntegerField(source='deal.id', read_only=True)

    class Meta:
        model = PurchaseConfirmation
        fields = [
            'id', 'deal', 'deal_id',
            'actual_item_price_rub',
            'item_photo_url', 'receipt_photo_url',
            'receipt_store_name', 'receipt_store_domain',
            'receipt_date', 'receipt_amount',
            'status', 'auto_check_passed', 'auto_check_details',
            'reviewed_by', 'reviewed_at', 'review_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'deal', 'status', 'auto_check_passed', 'auto_check_details',
            'reviewed_by', 'reviewed_at', 'review_notes',
            'created_at', 'updated_at'
        ]


class PurchaseConfirmationCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания подтверждения покупки байером."""

    class Meta:
        model = PurchaseConfirmation
        fields = [
            'actual_item_price_rub',
            'item_photo_url', 'receipt_photo_url'
        ]

    def validate_actual_item_price_rub(self, value: Decimal) -> Decimal:
        """Проверяем, что цена не превышает максимальную."""
        deal = self.context['deal']
        if value > deal.item_price_max_rub:
            raise serializers.ValidationError(
                f"Фактическая цена покупки ({value}) не может превышать "
                f"максимальную цену из заявки ({deal.item_price_max_rub})"
            )
        return value

    def create(self, validated_data: Dict[str, Any]) -> PurchaseConfirmation:
        """Создает подтверждение покупки."""
        deal = self.context['deal']
        
        # TODO: Здесь можно добавить логику автоматической проверки чека:
        # - Извлечение данных из чека (OCR, если есть)
        # - Сверка магазина с deal.item_store_domain
        # - Сверка суммы
        
        confirmation = PurchaseConfirmation.objects.create(
            deal=deal,
            **validated_data
        )
        
        # Обновляем actual_item_price_rub в Deal
        if validated_data.get('actual_item_price_rub'):
            deal.actual_item_price_rub = validated_data['actual_item_price_rub']
            deal.save()
        
        return confirmation


class ShippingAddressSerializer(serializers.ModelSerializer):
    """Сериализатор для адреса доставки (только для заказчика и админа)."""

    order_id = serializers.IntegerField(source='order.id', read_only=True)

    class Meta:
        model = ShippingAddress
        fields = [
            'id', 'order', 'order_id',
            'shipping_address_full',
            'country', 'city', 'postal_code',
            'street', 'building', 'apartment',
            'meeting_point',
            'delivery_instructions',
            'revealed_to_buyer', 'revealed_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'order', 'revealed_to_buyer', 'revealed_at',
            'created_at', 'updated_at'
        ]


class ShippingAddressForBuyerSerializer(serializers.ModelSerializer):
    """Сериализатор адреса доставки для байера (раскрывается после PURCHASED)."""

    order_id = serializers.IntegerField(source='order.id', read_only=True)

    class Meta:
        model = ShippingAddress
        fields = [
            'id', 'order_id',
            'shipping_address_full',
            'meeting_point',  # Для PERSONAL_HANDOVER
            'delivery_instructions',
            'revealed_at'
        ]
        read_only_fields = ['id', 'revealed_at']


class ShippingAddressCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания адреса доставки заказчиком."""

    class Meta:
        model = ShippingAddress
        fields = [
            'shipping_address_full',
            'country', 'city', 'postal_code',
            'street', 'building', 'apartment',
            'meeting_point',
            'delivery_instructions'
        ]
    
    def validate_delivery_instructions(self, value: str) -> str:
        """Фильтруем контактные данные из инструкций."""
        if value:
            from core.contact_filter import validate_text_no_contacts
            validate_text_no_contacts(value)
        return value

    def create(self, validated_data: Dict[str, Any]) -> ShippingAddress:
        """Создает адрес доставки."""
        order = self.context['order']
        
        return ShippingAddress.objects.create(
            order=order,
            **validated_data
        )
