#!/usr/bin/env python3
"""
Скрипт для тестирования API и деплоя контрактов Deal.

Использование:
    docker-compose exec web python3 test_api_deployment.py

Или с указанием base URL:
    docker-compose exec web python3 test_api_deployment.py --base-url http://localhost:8000
"""

import os
import sys
import django
import requests
import json
from decimal import Decimal
from typing import Dict, Any, Optional

# Настройка Django
# В контейнере рабочая директория уже /app/src (это папка buyer)
# Просто устанавливаем settings модуль - Django сам найдет нужные пути
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'buyer.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from core.models import (
    OrderRequest, Deal, BuyerProfile, ShippingAddress,
    OnchainDeal, OfficialStoreDomain
)

User = get_user_model()


def print_section(title: str):
    """Печатает заголовок секции."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def print_subsection(title: str):
    """Печатает подзаголовок."""
    print(f"\n--- {title} ---")


def check_prerequisites() -> tuple[Optional[User], Optional[User]]:
    """Проверяет наличие тестовых пользователей (customer и buyer)."""
    print_section("1. Проверка предварительных условий")
    
    # Ищем или создаем customer
    try:
        customer = User.objects.filter(phone_number='+79991234567').first()
        if not customer:
            customer = User.objects.create(
                phone_number='+79991234567',
                first_name='Test',
                last_name='Customer',
                is_active=True
            )
            customer.set_password('testpass123')
            customer.save()
            print(f"  ✓ Создан customer: {customer.phone_number}")
        else:
            print(f"  ✓ Найден customer: {customer.phone_number}")
    except Exception as e:
        print(f"  ✗ Ошибка создания customer: {e}")
        import traceback
        traceback.print_exc()
        return None, None
    
    # Ищем или создаем buyer profile
    try:
        buyer_user = User.objects.filter(phone_number='+79991234568').first()
        if not buyer_user:
            buyer_user = User.objects.create(
                phone_number='+79991234568',
                first_name='Test',
                last_name='Buyer',
                is_active=True
            )
            buyer_user.set_password('testpass123')
            buyer_user.save()
            print(f"  ✓ Создан buyer user: {buyer_user.phone_number}")
        else:
            print(f"  ✓ Найден buyer user: {buyer_user.phone_number}")
        
        # Создаем или обновляем BuyerProfile
        buyer_profile, created = BuyerProfile.objects.get_or_create(
            user=buyer_user,
            defaults={
                'ton_address': 'EQDtw5uP3QDaC_9F6H0f-gAdrjs_jp0bzbw5PyRzn9vW7mN6',  # Тестовый адрес
                'country': 'RU',
                'city': 'Moscow',
                'bio': 'Test buyer profile'
            }
        )
        if created:
            print(f"  ✓ Создан BuyerProfile для {buyer_user.phone_number}")
        else:
            print(f"  ✓ Найден BuyerProfile для {buyer_user.phone_number}")
    except Exception as e:
        print(f"  ✗ Ошибка создания buyer: {e}")
        return customer, None
    
    # Проверяем наличие официального магазина (для валидации)
    try:
        store, created = OfficialStoreDomain.objects.get_or_create(
            domain='wildberries.ru',
            defaults={
                'store_name': 'Wildberries',
                'status': OfficialStoreDomain.Status.VERIFIED
            }
        )
        if created:
            print(f"  ✓ Добавлен официальный магазин: {store.domain}")
        else:
            print(f"  ✓ Найден официальный магазин: {store.domain}")
    except Exception as e:
        print(f"  ⚠️  Ошибка проверки магазина: {e}")
    
    return customer, buyer_profile


def test_create_order_request(customer: User, base_url: str = 'http://localhost:8000') -> Optional[int]:
    """Тестирует создание OrderRequest через API."""
    print_section("2. Создание OrderRequest через API")
    
    # Получаем токен для customer (упрощенная версия - в реальности нужна JWT auth)
    # Для теста используем прямую работу с Django ORM
    # Используем транзакцию для отката при ошибках
    
    order_data = {
        'title': 'Test Order - Небольшой товар для теста',
        'description': 'Небольшой товар для тестирования деплоя контракта',
        'item_store_url': 'https://www.wildberries.ru/catalog/12345678/detail.aspx',
        'item_category': OrderRequest.ItemCategory.OTHER,
        # Минимальные суммы для теста (всего 2 TON на кошельке)
        # При курсе 250 RUB/TON: ~160 RUB ≈ 0.64 TON
        'max_item_price_rub': '100.00',  # ~0.4 TON
        'buyer_fee_rub': '20.00',  # ~0.08 TON
        'service_fee_rub': '30.00',  # ~0.12 TON
        'insurance_rub': '10.00',  # ~0.04 TON
        # Используем PERSONAL_HANDOVER для минимизации shipping (0 RUB)
        'shipping_weight_category': OrderRequest.ShippingWeightCategory.UP_TO_1KG,
        'allow_personal_handover': True,
        'allow_delivery_by_mail': False,  # Отключаем доставку почтой для минимизации суммы
        'country_from': 'RU',  # Внутри России для PERSONAL_HANDOVER
        'country_to': 'RU',
    }
    
    try:
        # Используем транзакцию для атомарности
        with transaction.atomic():
            # Создаем OrderRequest напрямую через ORM (для теста)
            order = OrderRequest.objects.create(
                customer=customer,
                **order_data
            )
            print(f"  ✓ OrderRequest создан: ID={order.id}")
            print(f"    Title: {order.title}")
            print(f"    Max price: {order.max_item_price_rub} RUB")
            print(f"    Status: {order.status}")
            
            # Создаем ShippingAddress (обязательно для создания Deal)
            shipping_address = ShippingAddress.objects.create(
                order=order,
                city='Moscow',
                country='RU',
                postal_code='101000',
                shipping_address_full='ул. Тверская, д. 1, кв. 10',
                street='ул. Тверская',
                building='1',
                apartment='10'
            )
            print(f"  ✓ ShippingAddress создан: ID={shipping_address.id}")
            
            return order.id
    except Exception as e:
        print(f"  ✗ Ошибка создания OrderRequest: {e}")
        import traceback
        traceback.print_exc()
        # Транзакция автоматически откатится при исключении
        return None


def test_create_deal(order_id: int, buyer_profile: BuyerProfile) -> Optional[int]:
    """Тестирует создание Deal через create_bid."""
    print_section("3. Создание Deal через create_bid")
    
    try:
        # Используем транзакцию для атомарности
        with transaction.atomic():
            order = OrderRequest.objects.get(id=order_id)
            
            # Создаем Deal напрямую (имитация create_bid action)
            from django.utils import timezone
            from datetime import timedelta
            from core.shipping_calculator import calculate_shipping_budget
            from core.models import Deal
            
            # Используем PERSONAL_HANDOVER для минимизации суммы (shipping = 0)
            delivery_mode = Deal.DeliveryMode.PERSONAL_HANDOVER
            
            # Рассчитываем shipping budget
            shipping_budget_rub = calculate_shipping_budget(
                country_from=order.country_from or 'CN',
                country_to=order.country_to or 'RU',
                weight_category=order.shipping_weight_category or OrderRequest.ShippingWeightCategory.UP_TO_1KG,
                delivery_mode=delivery_mode
            )
            
            # Рассчитываем total_reserved_amount_rub
            buyer_reward_rub = order.buyer_fee_rub or Decimal('100.00')
            total_reserved_amount_rub = (
                order.max_item_price_rub +
                buyer_reward_rub +
                order.service_fee_rub +
                order.insurance_rub +
                shipping_budget_rub
            )
            
            # Конвертируем в TON (заглушка - нужен реальный курс)
            rate_rub_ton = Decimal('250.0')
            
            deal = Deal.objects.create(
                order=order,
                customer=order.customer,
                buyer=buyer_profile,
                item_store_url=order.item_store_url or '',
                item_store_domain=order.item_store_domain or '',
                store_verified=order.store_verified,
                item_price_max_rub=order.max_item_price_rub,
                buyer_reward_rub=buyer_reward_rub,
                buyer_fee_rub=buyer_reward_rub,
                service_fee_rub=order.service_fee_rub,
                insurance_rub=order.insurance_rub,
                delivery_mode=delivery_mode,
                shipping_weight_category=order.shipping_weight_category,
                country_from=order.country_from or '',
                country_to=order.country_to or '',
                shipping_budget_rub=shipping_budget_rub,
                total_reserved_amount_rub=total_reserved_amount_rub,
                item_price_ton=order.max_item_price_rub / rate_rub_ton,
                buyer_fee_ton=buyer_reward_rub / rate_rub_ton,
                service_fee_ton=order.service_fee_rub / rate_rub_ton,
                insurance_ton=order.insurance_rub / rate_rub_ton,
                shipping_budget_ton=shipping_budget_rub / rate_rub_ton,
                purchase_deadline=timezone.now() + timedelta(days=1),
                ship_deadline=timezone.now() + timedelta(days=3),
                confirm_deadline=timezone.now() + timedelta(days=14),
                status=Deal.Status.NEW,
            )
            
            # Обновляем статус заявки
            order.status = OrderRequest.Status.MATCHED
            order.save()
            
            print(f"  ✓ Deal создан: ID={deal.id}")
            print(f"    Status: {deal.status}")
            print(f"    Item price: {deal.item_price_max_rub} RUB / {deal.item_price_ton} TON")
            print(f"    Shipping budget: {deal.shipping_budget_rub} RUB / {deal.shipping_budget_ton} TON")
            print(f"    Total reserved: {deal.total_reserved_amount_rub} RUB")
            
            return deal.id
    except Exception as e:
        print(f"  ✗ Ошибка создания Deal: {e}")
        import traceback
        traceback.print_exc()
        # Транзакция автоматически откатится при исключении
        return None


def test_trigger_deployment(deal_id: int):
    """Тестирует запуск Celery задачи для деплоя контракта."""
    print_section("4. Запуск деплоя контракта через Celery")
    
    try:
        from core.tasks import deploy_onchain_deal
        
        # Запускаем задачу синхронно (для теста)
        print(f"  → Запускаем задачу deploy_onchain_deal для Deal {deal_id}...")
        result = deploy_onchain_deal(deal_id)
        
        print(f"  ✓ Задача выполнена")
        print(f"    Result: {json.dumps(result, indent=2, default=str)}")
        
        # Проверяем OnchainDeal
        deal = Deal.objects.get(id=deal_id)
        try:
            onchain = OnchainDeal.objects.get(deal=deal)
            print(f"\n  ✓ OnchainDeal создан:")
            print(f"    Contract address: {onchain.contract_address}")
            print(f"    Deployed at: {onchain.deployed_at}")
        except OnchainDeal.DoesNotExist:
            print(f"  ⚠️  OnchainDeal не найден (возможно, деплой не удался)")
        
    except Exception as e:
        print(f"  ✗ Ошибка деплоя: {e}")
        import traceback
        traceback.print_exc()


def check_deployed_contract(deal_id: int):
    """Проверяет статус деплоя контракта."""
    print_section("5. Проверка статуса деплоя")
    
    try:
        deal = Deal.objects.get(id=deal_id)
        onchain = OnchainDeal.objects.filter(deal=deal).first()
        
        if not onchain:
            print("  ⚠️  OnchainDeal не найден")
            return
        
        print(f"  Contract address: {onchain.contract_address}")
        print(f"  Deployed at: {onchain.deployed_at}")
        print(f"  Metadata hash: {onchain.metadata_hash_hex}")
        
        if onchain.contract_address:
            print(f"\n  🔗 Проверьте контракт на TONScan:")
            print(f"     https://testnet.tonscan.org/address/{onchain.contract_address}")
            
            # Пытаемся получить информацию о контракте
            try:
                from core.ton_client import TonCenterClient
                client = TonCenterClient()
                
                address_info = client.get_address_information(onchain.contract_address)
                print(f"\n  📊 Информация о контракте:")
                print(f"     Balance: {address_info.get('balance', 'N/A')} nanoTON")
                print(f"     State: {address_info.get('state', 'N/A')}")
                
            except Exception as e:
                print(f"  ⚠️  Не удалось получить информацию о контракте: {e}")
        
    except Exception as e:
        print(f"  ✗ Ошибка проверки: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Основная функция тестирования."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test API and contract deployment')
    parser.add_argument(
        '--base-url',
        default='http://localhost:8000',
        help='Base URL for API (default: http://localhost:8000)'
    )
    parser.add_argument(
        '--skip-deployment',
        action='store_true',
        help='Skip contract deployment test'
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("  API и Деплой Контрактов - Тестирование")
    print("=" * 70)
    
    # 1. Проверка предварительных условий
    customer, buyer_profile = check_prerequisites()
    if not customer or not buyer_profile:
        print("\n✗ Не удалось подготовить тестовых пользователей")
        return 1
    
    # 2. Создание OrderRequest
    order_id = test_create_order_request(customer, args.base_url)
    if not order_id:
        print("\n✗ Не удалось создать OrderRequest")
        return 1
    
    # 3. Создание Deal
    deal_id = test_create_deal(order_id, buyer_profile)
    if not deal_id:
        print("\n✗ Не удалось создать Deal")
        return 1
    
    # 4. Деплой контракта (если не пропущен)
    if not args.skip_deployment:
        test_trigger_deployment(deal_id)
        check_deployed_contract(deal_id)
    else:
        print_section("4. Деплой контракта")
        print("  ⏭️  Пропущено (--skip-deployment)")
    
    print_section("Готово")
    print("  ✓ Все тесты выполнены")
    print(f"\n  📝 Созданные объекты:")
    print(f"     OrderRequest ID: {order_id}")
    print(f"     Deal ID: {deal_id}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

