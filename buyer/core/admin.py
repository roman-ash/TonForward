from django.contrib import admin
from .models import (
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


@admin.register(BuyerProfile)
class BuyerProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'city', 'country', 'rating', 'deals_completed']
    list_filter = ['country', 'city']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'ton_address']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(OfficialStoreDomain)
class OfficialStoreDomainAdmin(admin.ModelAdmin):
    list_display = ['domain', 'store_name', 'status', 'verified_by', 'verified_at', 'created_at']
    list_filter = ['status', 'verified_at', 'created_at']
    search_fields = ['domain', 'store_name', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('domain', 'store_name', 'status')
        }),
        ('Проверка', {
            'fields': ('verified_by', 'verified_at', 'notes')
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(OrderRequest)
class OrderRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title', 'customer', 'status', 'max_item_price_rub',
        'buyer_fee_rub', 'item_store_domain', 'store_verified', 'created_at'
    ]
    list_filter = ['status', 'store_verified', 'item_category', 'store_country', 'created_at']
    search_fields = ['title', 'description', 'item_store_url', 'item_store_domain', 'customer__first_name', 'customer__last_name']
    readonly_fields = ['created_at', 'updated_at', 'total_amount_rub', 'item_store_domain']
    fieldsets = (
        ('Основная информация', {
            'fields': ('customer', 'title', 'description', 'status', 'item_category')
        }),
        ('Магазин', {
            'fields': ('item_store_url', 'item_store_domain', 'store_verified', 'store_link', 'store_city', 'store_country')
        }),
        ('Финансы (RUB)', {
            'fields': (
                'max_item_price_rub', 'buyer_fee_rub',
                'service_fee_rub', 'insurance_rub', 'total_amount_rub'
            )
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'order', 'customer', 'buyer', 'status',
        'item_price_max_rub', 'actual_item_price_rub', 'item_price_ton', 'created_at'
    ]
    list_filter = ['status', 'store_verified', 'created_at', 'purchase_deadline']
    search_fields = [
        'order__title', 'item_store_domain', 'item_store_url',
        'customer__first_name', 'customer__last_name',
        'buyer__user__first_name', 'buyer__user__last_name'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'total_amount_ton',
        'is_purchase_deadline_expired', 'is_ship_deadline_expired',
        'is_confirm_deadline_expired'
    ]
    date_hierarchy = 'created_at'
    fieldsets = (
        ('Сделка', {
            'fields': ('order', 'customer', 'buyer', 'status')
        }),
        ('Магазин', {
            'fields': ('item_store_url', 'item_store_domain', 'store_verified')
        }),
        ('Суммы в рублях', {
            'fields': (
                'item_price_max_rub', 'actual_item_price_rub',
                'buyer_fee_rub', 'service_fee_rub', 'insurance_rub'
            )
        }),
        ('Суммы в TON', {
            'fields': (
                'item_price_ton', 'buyer_fee_ton',
                'service_fee_ton', 'insurance_ton', 'total_amount_ton'
            )
        }),
        ('Дедлайны', {
            'fields': (
                'purchase_deadline', 'ship_deadline', 'confirm_deadline',
                'is_purchase_deadline_expired', 'is_ship_deadline_expired',
                'is_confirm_deadline_expired'
            )
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(OnchainDeal)
class OnchainDealAdmin(admin.ModelAdmin):
    list_display = ['id', 'deal', 'contract_address', 'deployed_at']
    search_fields = ['contract_address', 'metadata_hash_hex', 'deal__id']
    readonly_fields = ['deployed_at', 'updated_at']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'deal', 'provider', 'amount_rub', 'status',
        'provider_payment_id', 'created_at'
    ]
    list_filter = ['status', 'provider', 'created_at']
    search_fields = ['provider_payment_id', 'deal__id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'deal', 'tracking_number', 'shipping_provider', 'shipped_at'
    ]
    list_filter = ['shipping_provider', 'shipped_at']
    search_fields = ['tracking_number', 'deal__id']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'deal', 'opened_by', 'reason_code', 'resolution',
        'resolved_by', 'created_at'
    ]
    list_filter = ['reason_code', 'resolution', 'created_at']
    search_fields = ['deal__id', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'deal', 'rated_by', 'rated_user', 'score', 'created_at'
    ]
    list_filter = ['score', 'created_at']
    search_fields = ['deal__id', 'comment']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PurchaseConfirmation)
class PurchaseConfirmationAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'deal', 'actual_item_price_rub', 'status', 'auto_check_passed',
        'reviewed_by', 'reviewed_at', 'created_at'
    ]
    list_filter = ['status', 'auto_check_passed', 'reviewed_at', 'created_at']
    search_fields = ['deal__id', 'receipt_store_name', 'receipt_store_domain']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Сделка', {
            'fields': ('deal', 'status')
        }),
        ('Данные покупки', {
            'fields': ('actual_item_price_rub', 'item_photo_url', 'receipt_photo_url')
        }),
        ('Данные из чека', {
            'fields': (
                'receipt_store_name', 'receipt_store_domain',
                'receipt_date', 'receipt_amount'
            )
        }),
        ('Проверка', {
            'fields': (
                'auto_check_passed', 'auto_check_details',
                'reviewed_by', 'reviewed_at', 'review_notes'
            )
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(ShippingAddress)
class ShippingAddressAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'order', 'city', 'country',
        'revealed_to_buyer', 'revealed_at', 'created_at'
    ]
    list_filter = ['revealed_to_buyer', 'revealed_at', 'created_at']
    search_fields = ['order__id', 'shipping_address_full', 'city', 'country']
    readonly_fields = ['created_at', 'updated_at', 'revealed_at']
    fieldsets = (
        ('Заказ', {
            'fields': ('order',)
        }),
        ('Адрес доставки', {
            'fields': (
                'shipping_address_full',
                'country', 'city', 'postal_code',
                'street', 'building', 'apartment'
            )
        }),
        ('Личная передача', {
            'fields': ('meeting_point', 'delivery_instructions'),
            'classes': ('collapse',)
        }),
        ('Раскрытие адреса', {
            'fields': ('revealed_to_buyer', 'revealed_at')
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at')
        }),
    )
