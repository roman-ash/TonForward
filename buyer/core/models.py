"""
Core models for the buyer platform.

Models include:
- BuyerProfile: профиль байера
- OrderRequest: заявка заказчика на покупку товара
- Deal: сделка между заказчиком и конкретным байером (off-chain)
- OnchainDeal: привязка к смарт-контракту в TON
- Payment: рублёвый платёж заказчика
- Shipment: данные об отправке (трек, квитанция)
- Dispute: спор по сделке
- Rating: рейтинг и отзывы
"""

from decimal import Decimal
from typing import Optional

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


class BuyerProfile(models.Model):
    """Профиль байера."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='buyer_profile'
    )
    ton_address = models.CharField(max_length=128, blank=True)
    bio = models.TextField(blank=True)
    country = models.CharField(max_length=64, blank=True)
    city = models.CharField(max_length=64, blank=True)
    rating = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)]
    )
    deals_completed = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Buyer Profile'
        verbose_name_plural = 'Buyer Profiles'

    def __str__(self) -> str:
        return f"BuyerProfile: {self.user.get_full_name()} ({self.city})"


class OrderRequest(models.Model):
    """Заявка заказчика на покупку товара."""

    class Status(models.TextChoices):
        OPEN = "OPEN", "Открыта"
        MATCHED = "MATCHED", "Найден байер"
        PAID = "PAID", "Оплачена"
        CANCELLED = "CANCELLED", "Отменена"
        COMPLETED = "COMPLETED", "Завершена"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='order_requests'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    store_link = models.URLField(blank=True)
    store_city = models.CharField(max_length=64)
    store_country = models.CharField(max_length=64)

    max_item_price_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    buyer_fee_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    service_fee_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    insurance_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.OPEN
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Order Request'
        verbose_name_plural = 'Order Requests'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Order #{self.id}: {self.title} ({self.status})"

    @property
    def total_amount_rub(self) -> Decimal:
        """Общая сумма заказа в рублях."""
        return (
            self.max_item_price_rub +
            self.buyer_fee_rub +
            self.service_fee_rub +
            self.insurance_rub
        )


class Deal(models.Model):
    """Сделка между заказчиком и конкретным байером (off-chain)."""

    class Status(models.TextChoices):
        NEW = "NEW", "Создана (байер выбран, оплата не выполнена)"
        FUNDED = "FUNDED", "Escrow на блокчейне профинансирован"
        PURCHASED = "PURCHASED", "Товар куплен"
        SHIPPED = "SHIPPED", "Товар отправлен"
        COMPLETED = "COMPLETED", "Завершена"
        CANCELLED_REFUND_CUSTOMER = "CANCELLED_REFUND_CUSTOMER", "Отменена (возврат заказчику)"
        CANCELLED_PAY_BUYER = "CANCELLED_PAY_BUYER", "Отменена (выплата байеру)"
        DISPUTE = "DISPUTE", "Спор"

    order = models.ForeignKey(
        OrderRequest,
        on_delete=models.PROTECT,
        related_name='deals'
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="customer_deals"
    )
    buyer = models.ForeignKey(
        BuyerProfile,
        on_delete=models.PROTECT,
        related_name="buyer_deals"
    )

    # Суммы в рублях (слепок на момент сделки)
    item_price_max_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    buyer_fee_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    service_fee_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    insurance_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Суммы в TON (слепок на дате конвертации)
    item_price_ton = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        validators=[MinValueValidator(Decimal('0.000000001'))]
    )
    buyer_fee_ton = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        validators=[MinValueValidator(Decimal('0.000000001'))]
    )
    service_fee_ton = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        default=Decimal('0.000000000'),
        validators=[MinValueValidator(Decimal('0.000000000'))]
    )
    insurance_ton = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        default=Decimal('0.000000000'),
        validators=[MinValueValidator(Decimal('0.000000000'))]
    )

    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.NEW
    )

    purchase_deadline = models.DateTimeField()
    ship_deadline = models.DateTimeField()
    confirm_deadline = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Deal'
        verbose_name_plural = 'Deals'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Deal #{self.id}: {self.order.title} ({self.status})"

    @property
    def total_amount_ton(self) -> Decimal:
        """Общая сумма сделки в TON."""
        return (
            self.item_price_ton +
            self.buyer_fee_ton +
            self.service_fee_ton +
            self.insurance_ton
        )

    def get_total_amount_rub(self) -> Decimal:
        """Вычисляет общую сумму сделки в рублях."""
        return (
            self.item_price_max_rub +
            self.buyer_fee_rub +
            self.service_fee_rub +
            self.insurance_rub
        )

    @property
    def is_purchase_deadline_expired(self) -> bool:
        """Проверка истечения дедлайна покупки."""
        return timezone.now() > self.purchase_deadline

    @property
    def is_ship_deadline_expired(self) -> bool:
        """Проверка истечения дедлайна отправки."""
        return timezone.now() > self.ship_deadline

    @property
    def is_confirm_deadline_expired(self) -> bool:
        """Проверка истечения дедлайна подтверждения."""
        return timezone.now() > self.confirm_deadline


class OnchainDeal(models.Model):
    """Привязка к смарт-контракту в TON."""

    deal = models.OneToOneField(
        Deal,
        on_delete=models.CASCADE,
        related_name='onchain_deal'
    )
    contract_address = models.CharField(max_length=128)  # TON address
    metadata_hash_hex = models.CharField(max_length=128)
    deployed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Onchain Deal'
        verbose_name_plural = 'Onchain Deals'

    def __str__(self) -> str:
        return f"OnchainDeal: {self.contract_address}"


class Payment(models.Model):
    """Рублёвый платёж заказчика."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "В обработке"
        SUCCESS = "SUCCESS", "Успешно"
        FAILED = "FAILED", "Ошибка"
        REFUNDED = "REFUNDED", "Возвращён"

    deal = models.OneToOneField(
        Deal,
        on_delete=models.PROTECT,
        related_name="payment"
    )
    provider = models.CharField(max_length=32)  # 'yookassa', 'tinkoff', 'mock'
    provider_payment_id = models.CharField(max_length=128, blank=True)
    amount_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Payment #{self.id}: {self.amount_rub} RUB ({self.status})"


class Shipment(models.Model):
    """Данные об отправке (трек, квитанция)."""

    deal = models.OneToOneField(
        Deal,
        on_delete=models.CASCADE,
        related_name='shipment'
    )
    tracking_number = models.CharField(max_length=255, blank=True)
    shipping_provider = models.CharField(max_length=128, blank=True)  # DHL, FedEx, etc.
    receipt_photo_url = models.URLField(blank=True)  # URL к фото квитанции
    shipped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Shipment'
        verbose_name_plural = 'Shipments'

    def __str__(self) -> str:
        return f"Shipment for Deal #{self.deal.id}: {self.tracking_number}"


class Dispute(models.Model):
    """Спор по сделке."""

    class ReasonCode(models.IntegerChoices):
        ITEM_NOT_RECEIVED = 1, "Товар не получен"
        ITEM_DAMAGED = 2, "Товар повреждён"
        ITEM_DOES_NOT_MATCH = 3, "Товар не соответствует описанию"
        OTHER = 99, "Другое"

    class Resolution(models.TextChoices):
        PENDING = "PENDING", "В рассмотрении"
        REFUND_CUSTOMER = "REFUND_CUSTOMER", "Возврат заказчику"
        PAY_BUYER = "PAY_BUYER", "Выплата байеру"
        SPLIT = "SPLIT", "Разделение"
        RESOLVED = "RESOLVED", "Разрешён"

    deal = models.OneToOneField(
        Deal,
        on_delete=models.CASCADE,
        related_name='dispute'
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='opened_disputes'
    )
    reason_code = models.IntegerField(choices=ReasonCode.choices)
    description = models.TextField()
    resolution = models.CharField(
        max_length=32,
        choices=Resolution.choices,
        default=Resolution.PENDING
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_disputes'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Dispute'
        verbose_name_plural = 'Disputes'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"Dispute #{self.id} for Deal #{self.deal.id} ({self.resolution})"


class Rating(models.Model):
    """Рейтинг и отзывы."""

    deal = models.OneToOneField(
        Deal,
        on_delete=models.CASCADE,
        related_name='rating'
    )
    rated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='given_ratings'
    )
    rated_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_ratings'
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rating'
        verbose_name_plural = 'Ratings'
        ordering = ['-created_at']
        # Гарантируем, что рейтинг можно оставить только один раз за сделку
        unique_together = [['deal', 'rated_by']]

    def __str__(self) -> str:
        return f"Rating {self.score}/5 by {self.rated_by} for Deal #{self.deal.id}"

