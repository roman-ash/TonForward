"""
Утилиты для расчета бюджета доставки (shipping_budget_rub).
"""

import os
from decimal import Decimal
from math import ceil
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


# Конфигурация курсов и маржи
EUR_TO_RUB_RATE = Decimal(os.getenv('EUR_TO_RUB_RATE', '100.0'))  # TODO: получать из сервиса курсов
SHIPPING_MARGIN = Decimal(os.getenv('SHIPPING_MARGIN', '0.1'))  # 10% запас
CUSTOMS_LIMIT_EUR = Decimal('200.0')  # Лимит таможенной пошлины


# Тарифы международной доставки (EUR)
# Структура: {(country_from, country_to, weight_category): price_eur}
INTERNATIONAL_SHIPPING_RATES: Dict[Tuple[str, str, str], Decimal] = {
    # Германия → Россия
    ('DE', 'RU', 'UP_TO_1KG'): Decimal('15.0'),
    ('DE', 'RU', 'FROM_1_TO_2KG'): Decimal('25.0'),
    ('DE', 'RU', 'FROM_2_TO_5KG'): Decimal('40.0'),
    ('DE', 'RU', 'FROM_5_TO_10KG'): Decimal('60.0'),
    ('DE', 'RU', 'OVER_10KG'): Decimal('90.0'),
    
    # Франция → Россия
    ('FR', 'RU', 'UP_TO_1KG'): Decimal('18.0'),
    ('FR', 'RU', 'FROM_1_TO_2KG'): Decimal('28.0'),
    ('FR', 'RU', 'FROM_2_TO_5KG'): Decimal('45.0'),
    ('FR', 'RU', 'FROM_5_TO_10KG'): Decimal('65.0'),
    ('FR', 'RU', 'OVER_10KG'): Decimal('95.0'),
    
    # США → Россия
    ('US', 'RU', 'UP_TO_1KG'): Decimal('25.0'),
    ('US', 'RU', 'FROM_1_TO_2KG'): Decimal('40.0'),
    ('US', 'RU', 'FROM_2_TO_5KG'): Decimal('60.0'),
    ('US', 'RU', 'FROM_5_TO_10KG'): Decimal('90.0'),
    ('US', 'RU', 'OVER_10KG'): Decimal('130.0'),
    
    # Италия → Россия
    ('IT', 'RU', 'UP_TO_1KG'): Decimal('16.0'),
    ('IT', 'RU', 'FROM_1_TO_2KG'): Decimal('26.0'),
    ('IT', 'RU', 'FROM_2_TO_5KG'): Decimal('42.0'),
    ('IT', 'RU', 'FROM_5_TO_10KG'): Decimal('62.0'),
    ('IT', 'RU', 'OVER_10KG'): Decimal('92.0'),
}

# Тарифы внутренней доставки (RUB)
# Структура: {(country, weight_category): price_rub}
DOMESTIC_SHIPPING_RATES: Dict[Tuple[str, str], Decimal] = {
    # Россия
    ('RU', 'UP_TO_1KG'): Decimal('300.0'),
    ('RU', 'FROM_1_TO_2KG'): Decimal('500.0'),
    ('RU', 'FROM_2_TO_5KG'): Decimal('800.0'),
    ('RU', 'FROM_5_TO_10KG'): Decimal('1200.0'),
    ('RU', 'OVER_10KG'): Decimal('2000.0'),
}


def get_international_rate(
    country_from: str,
    country_to: str,
    weight_category: str
) -> Decimal:
    """
    Получает базовый тариф международной доставки.
    
    Args:
        country_from: ISO код страны отправления (например, 'DE')
        country_to: ISO код страны назначения (например, 'RU')
        weight_category: Категория веса (например, 'UP_TO_1KG')
        
    Returns:
        Decimal: Тариф в EUR
        
    Raises:
        ValueError: Если тариф не найден
    """
    key = (country_from.upper(), country_to.upper(), weight_category)
    rate = INTERNATIONAL_SHIPPING_RATES.get(key)
    
    if rate is None:
        logger.warning(f"Тариф международной доставки не найден для {key}, используем средний тариф")
        # Используем средний тариф как fallback
        avg_rates_by_weight = {
            'UP_TO_1KG': Decimal('18.0'),
            'FROM_1_TO_2KG': Decimal('30.0'),
            'FROM_2_TO_5KG': Decimal('47.0'),
            'FROM_5_TO_10KG': Decimal('69.0'),
            'OVER_10KG': Decimal('102.0'),
        }
        rate = avg_rates_by_weight.get(weight_category, Decimal('50.0'))
        logger.info(f"Использован средний тариф: {rate} EUR для категории {weight_category}")
    
    return rate


def get_domestic_rate(country: str, weight_category: str) -> Decimal:
    """
    Получает базовый тариф внутренней доставки.
    
    Args:
        country: ISO код страны (например, 'RU')
        weight_category: Категория веса (например, 'UP_TO_1KG')
        
    Returns:
        Decimal: Тариф в RUB
        
    Raises:
        ValueError: Если тариф не найден
    """
    key = (country.upper(), weight_category)
    rate = DOMESTIC_SHIPPING_RATES.get(key)
    
    if rate is None:
        logger.warning(f"Тариф внутренней доставки не найден для {key}, используем средний тариф")
        # Используем средний тариф как fallback
        avg_rates_by_weight = {
            'UP_TO_1KG': Decimal('300.0'),
            'FROM_1_TO_2KG': Decimal('500.0'),
            'FROM_2_TO_5KG': Decimal('800.0'),
            'FROM_5_TO_10KG': Decimal('1200.0'),
            'OVER_10KG': Decimal('2000.0'),
        }
        rate = avg_rates_by_weight.get(weight_category, Decimal('800.0'))
        logger.info(f"Использован средний тариф: {rate} RUB для категории {weight_category}")
    
    return rate


def calculate_shipping_budget(
    country_from: str,
    country_to: str,
    weight_category: str,
    delivery_mode: str
) -> Decimal:
    """
    Рассчитывает бюджет на доставку (shipping_budget_rub).
    
    Args:
        country_from: ISO код страны отправления
        country_to: ISO код страны назначения
        weight_category: Категория веса/габарита
        delivery_mode: Режим доставки ('PERSONAL_HANDOVER', 'INTERNATIONAL_MAIL', 'DOMESTIC_MAIL')
        
    Returns:
        Decimal: Бюджет на доставку в рублях
        
    Raises:
        ValueError: Если delivery_mode некорректен
    """
    if delivery_mode == 'PERSONAL_HANDOVER':
        # Личная передача - бюджет 0
        return Decimal('0.00')
    
    elif delivery_mode == 'INTERNATIONAL_MAIL':
        # Международная пересылка
        base_cost_eur = get_international_rate(country_from, country_to, weight_category)
        
        # Конвертация в рубли с запасом
        shipping_budget_rub = Decimal(ceil(
            float(base_cost_eur * EUR_TO_RUB_RATE * (Decimal('1') + SHIPPING_MARGIN))
        ))
        
        # Округляем до 10 рублей
        shipping_budget_rub = Decimal(ceil(float(shipping_budget_rub) / 10)) * 10
        
        logger.info(
            f"INTERNATIONAL_MAIL: {country_from} → {country_to}, "
            f"{weight_category}: {base_cost_eur} EUR = {shipping_budget_rub} RUB"
        )
        
        return shipping_budget_rub
    
    elif delivery_mode == 'DOMESTIC_MAIL':
        # Внутренняя пересылка
        base_cost_rub = get_domestic_rate(country_to, weight_category)
        
        # Применяем запас
        shipping_budget_rub = Decimal(ceil(
            float(base_cost_rub * (Decimal('1') + SHIPPING_MARGIN))
        ))
        
        # Округляем до 10 рублей
        shipping_budget_rub = Decimal(ceil(float(shipping_budget_rub) / 10)) * 10
        
        logger.info(
            f"DOMESTIC_MAIL: {country_to}, "
            f"{weight_category}: {base_cost_rub} RUB → {shipping_budget_rub} RUB"
        )
        
        return shipping_budget_rub
    
    else:
        raise ValueError(f"Неизвестный режим доставки: {delivery_mode}")


def check_customs_limit(
    max_item_price_rub: Decimal,
    shipping_budget_rub: Decimal,
    eur_to_rub_rate: Decimal = None
) -> Tuple[bool, Decimal]:
    """
    Проверяет, не превышает ли сумма таможенный лимит.
    
    Args:
        max_item_price_rub: Максимальная цена товара в рублях
        shipping_budget_rub: Бюджет доставки в рублях
        eur_to_rub_rate: Курс EUR к RUB (по умолчанию из конфига)
        
    Returns:
        Tuple[bool, Decimal]:
            - True, если сумма в пределах лимита
            - Сумма в EUR для справки
    """
    if eur_to_rub_rate is None:
        eur_to_rub_rate = EUR_TO_RUB_RATE
    
    total_rub = max_item_price_rub + shipping_budget_rub
    total_eur = total_rub / eur_to_rub_rate
    
    is_within_limit = total_eur <= CUSTOMS_LIMIT_EUR
    
    return is_within_limit, total_eur

