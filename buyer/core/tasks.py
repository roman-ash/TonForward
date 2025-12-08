"""
Celery tasks for core app.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
import logging

from core.models import Deal, OnchainDeal, Payment
from core.ton_utils import call_contract_method, sync_deal_status_from_chain
from core.payment_webhook import (
    process_yookassa_webhook,
    process_tinkoff_webhook,
    process_mock_webhook
)

logger = logging.getLogger(__name__)


@shared_task(name='core.tasks.get_current_exchange_rate')
def get_current_exchange_rate(from_currency: str = 'BTC', to_currency: str = 'USD') -> dict:
    """
    Получает текущий курс валют.
    
    Args:
        from_currency: Исходная валюта (по умолчанию BTC)
        to_currency: Целевая валюта (по умолчанию USD)
    
    Returns:
        dict: Информация о курсе
    """
    try:
        # TODO: Реализовать получение реального курса через API
        # Например, через CoinGecko, Binance API и т.д.
        
        logger.info(
            f"Getting exchange rate: {from_currency} -> {to_currency} "
            f"at {timezone.now()}"
        )
        
        # Заглушка - возвращаем фиктивный курс
        # В будущем здесь должен быть реальный API запрос
        mock_rate = {
            'BTC': {'USD': 45000.0, 'RUB': 3375000.0},  # Примерный курс
            'TON': {'USD': 2.5, 'RUB': 187.5},  # Примерный курс TON
            'RUB': {'USD': 0.011, 'TON': 0.0053},  # Примерный курс RUB
        }
        
        rate = mock_rate.get(from_currency, {}).get(to_currency, 1.0)
        
        logger.info(f"Exchange rate {from_currency}/{to_currency}: {rate}")
        
        return {
            'from_currency': from_currency,
            'to_currency': to_currency,
            'rate': rate,
            'timestamp': timezone.now().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"Error getting exchange rate: {e}", exc_info=True)
        raise


@shared_task(name='core.tasks.check_deal_timeouts')
def check_deal_timeouts() -> dict:
    """
    Проверяет тайм-ауты сделок и вызывает соответствующие методы контрактов.

    Проверяет:
    - FUNDED с истекшим purchase_deadline → cancel_before_purchase
    - PURCHASED с истекшим ship_deadline → cancel_before_ship
    - SHIPPED с истекшим confirm_deadline → auto_complete_for_buyer

    Returns:
        dict: Статистика обработки тайм-аутов
    """
    now = timezone.now()
    stats = {
        'funded_expired': 0,
        'purchased_expired': 0,
        'shipped_expired': 0,
        'errors': 0
    }

    try:
        # Обрабатываем сделки FUNDED с истекшим purchase_deadline
        funded_expired = Deal.objects.filter(
            status=Deal.Status.FUNDED,
            purchase_deadline__lt=now
        ).select_related('onchain_deal')

        for deal in funded_expired:
            try:
                if hasattr(deal, 'onchain_deal'):
                    onchain_deal = deal.onchain_deal
                    logger.info(f"Cancelling deal {deal.id} before purchase (timeout)")
                    
                    # Вызываем метод cancel_before_purchase на контракте
                    result = call_contract_method(
                        onchain_deal.contract_address,
                        'cancel_before_purchase',
                        {}
                    )
                    
                    logger.info(f"Contract method result: {result}")
                    
                    # Синхронизируем статус с блокчейна
                    sync_deal_status_from_chain(onchain_deal)
                else:
                    # Если нет on-chain контракта, просто обновляем статус
                    logger.warning(f"Deal {deal.id} has no onchain_deal, updating status directly")
                    deal.status = Deal.Status.CANCELLED_REFUND_CUSTOMER
                    deal.save()
                
                stats['funded_expired'] += 1
                
            except Exception as e:
                logger.error(f"Error processing funded timeout for deal {deal.id}: {e}", exc_info=True)
                stats['errors'] += 1

        # Обрабатываем сделки PURCHASED с истекшим ship_deadline
        purchased_expired = Deal.objects.filter(
            status=Deal.Status.PURCHASED,
            ship_deadline__lt=now
        ).select_related('onchain_deal')

        for deal in purchased_expired:
            try:
                if hasattr(deal, 'onchain_deal'):
                    onchain_deal = deal.onchain_deal
                    logger.info(f"Cancelling deal {deal.id} before ship (timeout)")
                    
                    # Вызываем метод cancel_before_ship на контракте
                    result = call_contract_method(
                        onchain_deal.contract_address,
                        'cancel_before_ship',
                        {}
                    )
                    
                    logger.info(f"Contract method result: {result}")
                    
                    # Синхронизируем статус с блокчейна
                    sync_deal_status_from_chain(onchain_deal)
                else:
                    logger.warning(f"Deal {deal.id} has no onchain_deal, updating status directly")
                    deal.status = Deal.Status.CANCELLED_REFUND_CUSTOMER
                    deal.save()
                
                stats['purchased_expired'] += 1
                
            except Exception as e:
                logger.error(f"Error processing purchased timeout for deal {deal.id}: {e}", exc_info=True)
                stats['errors'] += 1

        # Обрабатываем сделки SHIPPED с истекшим confirm_deadline
        shipped_expired = Deal.objects.filter(
            status=Deal.Status.SHIPPED,
            confirm_deadline__lt=now
        ).select_related('onchain_deal')

        for deal in shipped_expired:
            try:
                if hasattr(deal, 'onchain_deal'):
                    onchain_deal = deal.onchain_deal
                    logger.info(f"Auto-completing deal {deal.id} for buyer (timeout)")
                    
                    # Вызываем метод auto_complete_for_buyer на контракте
                    result = call_contract_method(
                        onchain_deal.contract_address,
                        'auto_complete_for_buyer',
                        {}
                    )
                    
                    logger.info(f"Contract method result: {result}")
                    
                    # Синхронизируем статус с блокчейна
                    sync_deal_status_from_chain(onchain_deal)
                else:
                    logger.warning(f"Deal {deal.id} has no onchain_deal, updating status directly")
                    deal.status = Deal.Status.COMPLETED
                    deal.save()
                
                stats['shipped_expired'] += 1
                
            except Exception as e:
                logger.error(f"Error processing shipped timeout for deal {deal.id}: {e}", exc_info=True)
                stats['errors'] += 1

        logger.info(f"Deal timeout check completed: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Error in check_deal_timeouts: {e}", exc_info=True)
        stats['errors'] += 1
        raise


@shared_task(name='core.tasks.process_payment_webhook')
def process_payment_webhook(provider: str, webhook_data: dict) -> dict:
    """
    Обрабатывает webhook от платежного провайдера.

    Args:
        provider: Имя провайдера ('yookassa', 'tinkoff', 'mock')
        webhook_data: Данные webhook

    Returns:
        dict: Результат обработки
    """
    logger.info(f"Processing payment webhook from {provider}")

    try:
        if provider == 'yookassa':
            process_yookassa_webhook(webhook_data)
        elif provider == 'tinkoff':
            process_tinkoff_webhook(webhook_data)
        elif provider == 'mock':
            process_mock_webhook(webhook_data)
        else:
            logger.error(f"Unknown payment provider: {provider}")
            return {'error': f'Unknown provider: {provider}'}

        return {'status': 'processed', 'provider': provider}

    except Exception as e:
        logger.error(f"Error processing payment webhook: {e}", exc_info=True)
        raise


@shared_task(name='core.tasks.deploy_onchain_deal')
def deploy_onchain_deal(deal_id: int) -> dict:
    """
    Деплоит on-chain контракт для сделки.

    Args:
        deal_id: ID сделки

    Returns:
        dict: Результат деплоя
    """
    from core.models import Deal, OnchainDeal
    from core.ton_utils import (
        deploy_onchain_deal as deploy_contract,
        DealOnchainParams,
        convert_ton_to_nano,
        calculate_metadata_hash
    )
    import os

    try:
        deal = Deal.objects.get(pk=deal_id)
        
        # Проверяем, что on-chain контракт еще не создан
        if hasattr(deal, 'onchain_deal'):
            logger.warning(f"Deal {deal_id} already has onchain_deal")
            return {'error': 'Onchain deal already exists'}

        # Получаем адреса из настроек
        service_wallet = os.environ.get('TON_SERVICE_WALLET', '')
        arbiter_wallet = os.environ.get('TON_ARBITER_WALLET', '')
        
        # Получаем адрес байера (обязателен)
        buyer_ton_address = deal.buyer.ton_address or ''
        
        # Получаем адрес заказчика (если есть, иначе используем service_wallet)
        if hasattr(deal.customer, 'buyer_profile') and deal.customer.buyer_profile.ton_address:
            customer_ton_address = deal.customer.buyer_profile.ton_address
        else:
            # Если у заказчика нет TON-адреса, используем service_wallet
            customer_ton_address = service_wallet
            logger.info(f"Customer {deal.customer.id} has no TON address, using service_wallet as customer_address")
        
        if not all([service_wallet, arbiter_wallet, buyer_ton_address]):
            logger.error(f"Missing required TON addresses for deal {deal_id}")
            return {'error': 'Missing required TON addresses: service_wallet, arbiter_wallet, buyer_ton_address'}

        # Подготавливаем параметры
        deal_data = {
            'deal_id': deal.id,
            'order_title': deal.order.title,
            'created_at': deal.created_at.isoformat(),
        }
        metadata_hash = calculate_metadata_hash(deal_data)

        params = DealOnchainParams(
            customer_address=customer_ton_address,
            buyer_address=buyer_ton_address,
            service_wallet=service_wallet,
            arbiter_wallet=arbiter_wallet,
            item_price_nano=convert_ton_to_nano(deal.item_price_ton),
            buyer_fee_nano=convert_ton_to_nano(deal.buyer_fee_ton),
            service_fee_nano=convert_ton_to_nano(deal.service_fee_ton),
            insurance_nano=convert_ton_to_nano(deal.insurance_ton),
            purchase_deadline_ts=int(deal.purchase_deadline.timestamp()),
            ship_deadline_ts=int(deal.ship_deadline.timestamp()),
            confirm_deadline_ts=int(deal.confirm_deadline.timestamp()),
            metadata_hash_cell=metadata_hash
        )

        # Деплоим контракт
        contract_address = deploy_contract(params)

        # Создаем запись OnchainDeal
        with transaction.atomic():
            onchain_deal = OnchainDeal.objects.create(
                deal=deal,
                contract_address=contract_address,
                metadata_hash_hex=metadata_hash.hex()
            )

            # Обновляем статус сделки
            deal.status = Deal.Status.FUNDED
            deal.save()

        logger.info(f"Deployed onchain deal for deal {deal_id}: {contract_address}")

        return {
            'deal_id': deal_id,
            'contract_address': contract_address,
            'status': 'deployed'
        }

    except Deal.DoesNotExist:
        logger.error(f"Deal {deal_id} not found")
        return {'error': f'Deal {deal_id} not found'}
    except Exception as e:
        logger.error(f"Error deploying onchain deal for deal {deal_id}: {e}", exc_info=True)
        raise

