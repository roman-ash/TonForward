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


class OfficialStoreDomain(models.Model):
    """Whitelist официальных магазинов и маркетплейсов."""
    
    class Status(models.TextChoices):
        VERIFIED = "VERIFIED", "Проверен (разрешён)"
        PENDING = "PENDING", "На проверке (условно разрешён)"
        REJECTED = "REJECTED", "Отклонён (чёрный список)"
    
    domain = models.CharField(
        max_length=255,
        unique=True,
        verbose_name='Домен',
        help_text='Например: amazon.com, wildberries.ru'
    )
    store_name = models.CharField(
        max_length=255,
        verbose_name='Название магазина'
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Статус проверки'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Примечания',
        help_text='Дополнительная информация о магазине'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_stores',
        verbose_name='Проверил'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Official Store Domain'
        verbose_name_plural = 'Official Store Domains'
        ordering = ['domain']

    def __str__(self) -> str:
        return f"{self.domain} ({self.get_status_display()})"


class OrderRequest(models.Model):
    """Заявка заказчика на покупку товара."""

    class Status(models.TextChoices):
        OPEN = "OPEN", "Открыта"
        MATCHED = "MATCHED", "Найден байер"
        PAID = "PAID", "Оплачена"
        CANCELLED = "CANCELLED", "Отменена"
        COMPLETED = "COMPLETED", "Завершена"

    class ItemCategory(models.TextChoices):
        ELECTRONICS = "ELECTRONICS", "Электроника"
        CLOTHING = "CLOTHING", "Одежда и обувь"
        COSMETICS = "COSMETICS", "Косметика и парфюмерия"
        FOOD = "FOOD", "Продукты питания"
        BOOKS = "BOOKS", "Книги"
        TOYS = "TOYS", "Игрушки"
        SPORTS = "SPORTS", "Спорт и отдых"
        HOME = "HOME", "Товары для дома"
        JEWELRY = "JEWELRY", "Ювелирные изделия"
        OTHER = "OTHER", "Другое"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='order_requests'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Ссылка на товар в официальном магазине (обязательное поле)
    item_store_url = models.URLField(
        verbose_name='Ссылка на товар в магазине',
        help_text='Ссылка на страницу товара в официальном магазине/маркетплейсе',
        blank=True,  # Временно для миграции существующих записей
        null=True,   # Разрешаем NULL в БД для существующих записей
        default=''
    )
    
    # Домен магазина (автоматически заполняется)
    item_store_domain = models.CharField(
        max_length=255,
        verbose_name='Домен магазина',
        help_text='Домен магазина, извлеченный из URL',
        blank=True,  # Временно для миграции существующих записей
        null=True,   # Разрешаем NULL в БД для существующих записей
        default=''
    )
    
    # Признак проверки магазина
    store_verified = models.BooleanField(
        default=False,
        verbose_name='Магазин проверен',
        help_text='Магазин прошел проверку (авто или ручная)'
    )
    
    # Категория товара
    item_category = models.CharField(
        max_length=64,
        choices=ItemCategory.choices,
        default=ItemCategory.OTHER,
        verbose_name='Категория товара'
    )
    
    # Категория веса/габарита для расчета доставки
    class ShippingWeightCategory(models.TextChoices):
        UP_TO_1KG = "UP_TO_1KG", "До 1 кг"
        FROM_1_TO_2KG = "FROM_1_TO_2KG", "1-2 кг"
        FROM_2_TO_5KG = "FROM_2_TO_5KG", "2-5 кг"
        FROM_5_TO_10KG = "FROM_5_TO_10KG", "5-10 кг"
        OVER_10KG = "OVER_10KG", "Более 10 кг"
    
    shipping_weight_category = models.CharField(
        max_length=32,
        choices=ShippingWeightCategory.choices,
        default=ShippingWeightCategory.UP_TO_1KG,
        verbose_name='Категория веса/габарита',
        help_text='Категория веса/габарита для расчета стоимости доставки'
    )
    
    # Разрешенные форматы доставки
    allow_personal_handover = models.BooleanField(
        default=True,
        verbose_name='Разрешена личная встреча',
        help_text='Заказчик допускает личную передачу товара'
    )
    allow_delivery_by_mail = models.BooleanField(
        default=True,
        verbose_name='Разрешена доставка почтой',
        help_text='Заказчик допускает доставку почтой/курьером'
    )
    
    # Страны/города
    country_from = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Страна покупки',
        help_text='Страна, где будет покупаться товар (ISO код, например: DE, FR)'
    )
    country_to = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Страна получения',
        help_text='Страна, куда будет доставлен товар (ISO код, например: RU)'
    )
    
    # Старые поля (оставляем для обратной совместимости, но помечаем как deprecated)
    store_link = models.URLField(blank=True, help_text='DEPRECATED: используйте item_store_url')
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

    # Информация о магазине (копируется из OrderRequest)
    item_store_url = models.URLField(
        verbose_name='Ссылка на товар в магазине',
        blank=True,  # Временно для миграции существующих записей
        null=True,   # Разрешаем NULL в БД для существующих записей
        default=''
    )
    item_store_domain = models.CharField(
        max_length=255,
        verbose_name='Домен магазина',
        blank=True,  # Временно для миграции существующих записей
        null=True,   # Разрешаем NULL в БД для существующих записей
        default=''
    )
    store_verified = models.BooleanField(
        default=False,
        verbose_name='Магазин проверен'
    )
    
    # Фактическая цена покупки (заполняется байером при подтверждении покупки)
    actual_item_price_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Фактическая цена покупки',
        help_text='Цена товара по чеку (заполняется после покупки)'
    )
    
    # Режим доставки (выбирается при создании Deal)
    class DeliveryMode(models.TextChoices):
        PERSONAL_HANDOVER = "PERSONAL_HANDOVER", "Личная передача"
        INTERNATIONAL_MAIL = "INTERNATIONAL_MAIL", "Международная почта"
        DOMESTIC_MAIL = "DOMESTIC_MAIL", "Внутренняя почта"
    
    delivery_mode = models.CharField(
        max_length=32,
        choices=DeliveryMode.choices,
        blank=True,  # Временно для миграции существующих записей
        null=True,   # Временно для миграции существующих записей
        verbose_name='Режим доставки',
        help_text='Способ доставки товара (выбирается байером при создании сделки)'
    )
    
    # Категория веса (копируется из OrderRequest)
    shipping_weight_category = models.CharField(
        max_length=32,
        choices=OrderRequest.ShippingWeightCategory.choices,
        blank=True,  # Временно для миграции существующих записей
        null=True,   # Временно для миграции существующих записей
        verbose_name='Категория веса/габарита'
    )
    
    # Страны (копируются из OrderRequest)
    country_from = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Страна покупки'
    )
    country_to = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Страна получения'
    )
    
    # Фактическая стоимость доставки (заполняется при отправке)
    actual_shipping_cost_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Фактическая стоимость доставки',
        help_text='Стоимость доставки по чеку (заполняется при отправке товара)'
    )
    
    # Суммы в рублях (слепок на момент сделки)
    item_price_max_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    buyer_reward_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Вознаграждение байеру',
        help_text='Вознаграждение байеру за покупку и доставку'
    )
    
    # Старое поле (deprecated, оставляем для обратной совместимости)
    buyer_fee_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='DEPRECATED: используйте buyer_reward_rub'
    )
    
    service_fee_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    # Бюджет на доставку (рассчитывается при создании Deal)
    shipping_budget_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Бюджет на доставку',
        help_text='Зарезервированный бюджет на доставку (рассчитывается при создании сделки)'
    )
    
    # Общая сумма, резервируемая с заказчика
    total_reserved_amount_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Общая сумма резервирования',
        help_text='Сумма, которая должна быть зарезервирована с заказчика при оплате'
    )
    
    # Остаток после выплаты байеру (для обработки по бизнес-правилам)
    remainder_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Остаток после выплаты',
        help_text='Остаток средств после выплаты байеру (может быть возвращен заказчику или остаться у сервиса)'
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
    
    # Бюджет на доставку в TON (конвертируется из shipping_budget_rub)
    shipping_budget_ton = models.DecimalField(
        max_digits=18,
        decimal_places=9,
        null=True,
        blank=True,
        default=Decimal('0.000000000'),
        validators=[MinValueValidator(Decimal('0.000000000'))],
        verbose_name='Бюджет на доставку в TON',
        help_text='Бюджет на доставку в TON (конвертируется из shipping_budget_rub при создании сделки)'
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
        """
        Общая сумма сделки в рублях.
        Использует total_reserved_amount_rub, если он заполнен, иначе рассчитывает.
        """
        if hasattr(self, 'total_reserved_amount_rub') and self.total_reserved_amount_rub:
            return self.total_reserved_amount_rub
        
        # Обратная совместимость: используем старую логику
        buyer_fee = self.buyer_reward_rub if hasattr(self, 'buyer_reward_rub') and self.buyer_reward_rub else (self.buyer_fee_rub or Decimal('0'))
        shipping_budget = self.shipping_budget_rub if hasattr(self, 'shipping_budget_rub') and self.shipping_budget_rub else Decimal('0')
        return (
            self.item_price_max_rub +
            buyer_fee +
            self.service_fee_rub +
            shipping_budget +
            self.insurance_rub
        )
    
    def calculate_buyer_payout_rub(self) -> Decimal:
        """
        Рассчитывает сумму выплаты байеру.
        
        buyer_payout_rub = actual_item_price_rub + actual_shipping_cost_rub + buyer_reward_rub
        """
        if not self.actual_item_price_rub:
            raise ValueError("actual_item_price_rub не заполнен")
        
        buyer_reward = self.buyer_reward_rub if hasattr(self, 'buyer_reward_rub') and self.buyer_reward_rub else (self.buyer_fee_rub or Decimal('0'))
        actual_shipping = self.actual_shipping_cost_rub if hasattr(self, 'actual_shipping_cost_rub') and self.actual_shipping_cost_rub else Decimal('0')
        
        return (
            self.actual_item_price_rub +
            actual_shipping +
            buyer_reward
        )
    
    def calculate_remainder_rub(self, blockchain_fees_rub: Decimal = Decimal('0.00')) -> Decimal:
        """
        Рассчитывает остаток после выплаты байеру.
        
        remainder_rub = total_reserved_amount_rub - buyer_payout_rub - blockchain_fees_rub
        
        Args:
            blockchain_fees_rub: Комиссии блокчейна за транзакции (по умолчанию 0)
            
        Returns:
            Decimal: Остаток в рублях
        """
        if not self.total_reserved_amount_rub:
            raise ValueError("total_reserved_amount_rub не заполнен")
        
        buyer_payout = self.calculate_buyer_payout_rub()
        remainder = self.total_reserved_amount_rub - buyer_payout - blockchain_fees_rub
        
        # Остаток не может быть отрицательным (если buyer_payout больше зарезервированного)
        return max(remainder, Decimal('0.00'))

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


class ShippingAddress(models.Model):
    """
    Адрес доставки для заказа.
    Хранится отдельно от Deal для контроля раскрытия информации.
    
    Примечание: delivery_mode определяется в Deal, не в ShippingAddress.
    """
    
    order = models.OneToOneField(
        'OrderRequest',
        on_delete=models.CASCADE,
        related_name='shipping_address'
    )
    
    # Полный адрес (для почты)
    shipping_address_full = models.TextField(
        verbose_name='Полный адрес доставки',
        help_text='Почтовый адрес или адрес ПВЗ'
    )
    
    # Разбивка адреса (опционально, для удобства)
    country = models.CharField(max_length=64, blank=True)
    city = models.CharField(max_length=128, blank=True)
    postal_code = models.CharField(max_length=32, blank=True)
    street = models.TextField(blank=True)
    building = models.CharField(max_length=32, blank=True)
    apartment = models.CharField(max_length=32, blank=True)
    
    # Для личной передачи - точка встречи
    meeting_point = models.TextField(
        blank=True,
        verbose_name='Точка встречи',
        help_text='Публичное место для личной передачи (для PERSONAL_HANDOVER)'
    )
    
    # Примечание: delivery_mode хранится в Deal, не в ShippingAddress
    # delivery_mode определяется при создании Deal байером
    
    delivery_instructions = models.TextField(
        blank=True,
        verbose_name='Инструкции по доставке',
        help_text='Дополнительные инструкции от заказчика'
    )
    
    # Флаг раскрытия адреса байеру
    revealed_to_buyer = models.BooleanField(
        default=False,
        verbose_name='Адрес раскрыт байеру',
        help_text='Адрес был раскрыт байеру после подтверждения покупки'
    )
    revealed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата раскрытия'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Shipping Address'
        verbose_name_plural = 'Shipping Addresses'

    def __str__(self) -> str:
        return f"Address for Order #{self.order.id} ({self.country}, {self.city})"


class PurchaseConfirmation(models.Model):
    """Подтверждение покупки байером с чеком и фото."""
    
    class Status(models.TextChoices):
        PENDING = "PENDING", "На проверке"
        APPROVED = "APPROVED", "Одобрено"
        REJECTED = "REJECTED", "Отклонено"
        NEEDS_REVIEW = "NEEDS_REVIEW", "Требуется ручная проверка"
    
    deal = models.OneToOneField(
        'Deal',
        on_delete=models.CASCADE,
        related_name='purchase_confirmation'
    )
    
    # Фактическая цена (может быть заполнена вручную или извлечена из чека)
    actual_item_price_rub = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Фактическая цена покупки'
    )
    
    # Фото товара
    item_photo_url = models.URLField(
        blank=True,
        verbose_name='Фото товара',
        help_text='URL к фотографии купленного товара'
    )
    
    # Чек покупки
    receipt_photo_url = models.URLField(
        blank=True,
        verbose_name='Фото чека',
        help_text='URL к фотографии чека покупки'
    )
    
    # Данные, извлеченные из чека (опционально, для авто-проверки)
    receipt_store_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Название магазина из чека'
    )
    receipt_store_domain = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Домен магазина из чека'
    )
    receipt_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата покупки из чека'
    )
    receipt_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Сумма из чека'
    )
    
    # Статус проверки
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Статус проверки'
    )
    
    # Результаты автоматической проверки
    auto_check_passed = models.BooleanField(
        default=False,
        verbose_name='Автопроверка пройдена'
    )
    auto_check_details = models.TextField(
        blank=True,
        verbose_name='Детали автопроверки',
        help_text='Лог автоматической проверки (сверка магазина, суммы и т.д.)'
    )
    
    # Ручная модерация
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_purchases',
        verbose_name='Проверил'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата проверки'
    )
    review_notes = models.TextField(
        blank=True,
        verbose_name='Примечания модератора'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Purchase Confirmation'
        verbose_name_plural = 'Purchase Confirmations'

    def __str__(self) -> str:
        return f"Purchase Confirmation for Deal #{self.deal.id} ({self.status})"


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

