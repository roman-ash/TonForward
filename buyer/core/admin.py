from django.contrib import admin
from .models import (
    BuyerProfile,
    OrderRequest,
    Deal,
    OnchainDeal,
    Payment,
    Shipment,
    Dispute,
    Rating
)


@admin.register(BuyerProfile)
class BuyerProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'city', 'country', 'rating', 'deals_completed']
    list_filter = ['country', 'city']
    search_fields = ['user__first_name', 'user__last_name', 'user__email', 'ton_address']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(OrderRequest)
class OrderRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'title', 'customer', 'status', 'max_item_price_rub',
        'buyer_fee_rub', 'store_city', 'created_at'
    ]
    list_filter = ['status', 'store_country', 'created_at']
    search_fields = ['title', 'description', 'customer__first_name', 'customer__last_name']
    readonly_fields = ['created_at', 'updated_at', 'total_amount_rub']
    fieldsets = (
        ('Основная информация', {
            'fields': ('customer', 'title', 'description', 'status')
        }),
        ('Детали магазина', {
            'fields': ('store_link', 'store_city', 'store_country')
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
        'item_price_max_rub', 'item_price_ton', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'purchase_deadline']
    search_fields = [
        'order__title', 'customer__first_name', 'customer__last_name',
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
        ('Суммы в рублях', {
            'fields': (
                'item_price_max_rub', 'buyer_fee_rub',
                'service_fee_rub', 'insurance_rub'
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
