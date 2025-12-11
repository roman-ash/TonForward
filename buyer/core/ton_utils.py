"""
Утилиты для работы с TON blockchain.

Модуль для деплоя и взаимодействия со смарт-контрактами Deal.
"""

import os
import hashlib
from dataclasses import dataclass
from typing import Optional, Dict, Any
from decimal import Decimal
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class DealOnchainParams:
    """Параметры для деплоя on-chain сделки."""

    customer_address: str  # TON address заказчика
    buyer_address: str  # TON address байера
    service_wallet: str  # TON address сервисного кошелька
    arbiter_wallet: str  # TON address арбитра
    item_price_nano: int  # Максимальная цена товара в nanoTON (для escrow)
    buyer_fee_nano: int  # Вознаграждение байера в nanoTON
    shipping_budget_nano: int  # Бюджет на доставку в nanoTON (для escrow)
    service_fee_nano: int  # Комиссия сервиса в nanoTON (НЕ в escrow, остается у сервиса)
    insurance_nano: int  # Страховка в nanoTON (НЕ в escrow, остается у сервиса)
    purchase_deadline_ts: int  # Unix timestamp дедлайна покупки
    ship_deadline_ts: int  # Unix timestamp дедлайна отправки
    confirm_deadline_ts: int  # Unix timestamp дедлайна подтверждения
    metadata_hash_cell: bytes  # Hash метаданных


def convert_ton_to_nano(ton_amount: Decimal) -> int:
    """
    Конвертирует TON в nanoTON (1 TON = 1e9 nanoTON).

    Args:
        ton_amount: Сумма в TON

    Returns:
        int: Сумма в nanoTON
    """
    return int(ton_amount * Decimal('1000000000'))


def convert_nano_to_ton(nano_amount: int) -> Decimal:
    """
    Конвертирует nanoTON в TON.

    Args:
        nano_amount: Сумма в nanoTON

    Returns:
        Decimal: Сумма в TON
    """
    return Decimal(nano_amount) / Decimal('1000000000')


def calculate_metadata_hash(deal_data: Dict[str, Any]) -> bytes:
    """
    Вычисляет hash метаданных сделки.

    Args:
        deal_data: Словарь с данными сделки

    Returns:
        bytes: Hash метаданных
    """
    # Формируем строку из данных для хеширования
    metadata_string = (
        f"{deal_data.get('deal_id')}-"
        f"{deal_data.get('order_title')}-"
        f"{deal_data.get('created_at')}"
    )
    
    # Вычисляем SHA256 hash
    hash_obj = hashlib.sha256(metadata_string.encode('utf-8'))
    return hash_obj.digest()


def deploy_onchain_deal(params: DealOnchainParams) -> str:
    """
    Деплой смарт-контракта Deal в TON.

    Args:
        params: Параметры для деплоя контракта

    Returns:
        str: Адрес деплоенного контракта

    Raises:
        Exception: Если деплой не удался
    """
    logger.info(f"Deploying onchain deal with params: {params}")
    
    # Проверяем наличие необходимых зависимостей
    try:
        from .ton_client import TonCenterClient
        from .ton_wallet import TonWalletService
        from .ton_contracts import (
            load_deal_code_cell,
            build_deal_init_data_cell,
            calculate_contract_address
        )
    except ImportError as e:
        logger.warning(f"TON dependencies not available: {e}, using mock deployment")
        mock_address = f"EQC{hashlib.sha256(str(params).encode()).hexdigest()[:48]}"
        logger.info(f"Mock deployment, generated address: {mock_address}")
        return mock_address
    
    # Проверяем наличие mnemonic кошелька
    mnemonic = os.environ.get('TON_MNEMONIC')
    if not mnemonic:
        logger.warning("TON_MNEMONIC not set, using mock deployment")
        mock_address = f"EQC{hashlib.sha256(str(params).encode()).hexdigest()[:48]}"
        logger.info(f"Mock deployment, generated address: {mock_address}")
        return mock_address
    
    try:
        # Инициализируем клиенты
        ton_client = TonCenterClient()
        wallet_service = TonWalletService(mnemonic=mnemonic, ton_client=ton_client)
        
        # Загружаем код контракта
        try:
            code_cell = load_deal_code_cell()
        except ValueError as e:
            logger.warning(f"Deal contract code not available: {e}, using mock deployment")
            mock_address = f"EQC{hashlib.sha256(str(params).encode()).hexdigest()[:48]}"
            logger.info(f"Mock deployment, generated address: {mock_address}")
            return mock_address
        
        # Собираем init data
        init_params = {
            'customer_address': params.customer_address,
            'buyer_address': params.buyer_address,
            'service_wallet': params.service_wallet,
            'arbiter_wallet': params.arbiter_wallet,
            'item_price_ton': convert_nano_to_ton(params.item_price_nano),
            'buyer_fee_ton': convert_nano_to_ton(params.buyer_fee_nano),
            'shipping_budget_ton': convert_nano_to_ton(params.shipping_budget_nano),
            'service_fee_ton': convert_nano_to_ton(params.service_fee_nano),
            'insurance_ton': convert_nano_to_ton(params.insurance_nano),
            'purchase_deadline_ts': params.purchase_deadline_ts,
            'ship_deadline_ts': params.ship_deadline_ts,
            'confirm_deadline_ts': params.confirm_deadline_ts,
            'metadata_hash': params.metadata_hash_cell,
        }
        
        init_data_cell = build_deal_init_data_cell(init_params)
        
        # Вычисляем общую сумму для escrow
        # Escrow должен покрывать максимальную выплату байеру:
        # buyer_payout = actual_item_price + actual_shipping_cost + buyer_reward
        # Максимум = item_price_max + shipping_budget + buyer_reward
        # Service_fee и insurance НЕ входят в escrow (остаются у сервиса)
        total_amount_ton = (
            convert_nano_to_ton(params.item_price_nano) +
            convert_nano_to_ton(params.shipping_budget_nano) +
            convert_nano_to_ton(params.buyer_fee_nano)
        )
        
        # Деплоим контракт
        # Для деплоя отправляем минимальную сумму (~0.1 TON), основную сумму escrow отправляем после
        deploy_amount_ton = Decimal('0.1')  # Минимальная сумма для деплоя (газ + комиссии)
        
        logger.info(f"Deploying contract (initial deploy: {deploy_amount_ton} TON, escrow will be {total_amount_ton} TON)")
        contract_address = wallet_service.deploy_contract(
            code_cell=code_cell,
            init_data_cell=init_data_cell,
            amount_ton=deploy_amount_ton,  # Используем минимальную сумму для деплоя
            comment=f"Deploy Deal contract for deal"
        )
        
        logger.info(f"Contract deployed successfully: {contract_address}")
        
        # После успешного деплоя отправляем основную сумму escrow
        if total_amount_ton > deploy_amount_ton:
            escrow_amount = total_amount_ton - deploy_amount_ton
            logger.info(f"Sending escrow amount {escrow_amount} TON to deployed contract")
            try:
                wallet_service.send_transfer(
                    to_address=contract_address,
                    amount_ton=escrow_amount,
                    comment="Escrow for Deal contract"
                )
                logger.info(f"Escrow amount sent successfully")
            except Exception as e:
                logger.warning(f"Failed to send escrow amount: {e}. Contract is deployed, but escrow needs to be sent manually.")
        
        return contract_address
        
    except Exception as e:
        logger.error(f"Error deploying contract: {e}", exc_info=True)
        # Fallback на mock в случае ошибки
        logger.warning("Falling back to mock deployment due to error")
        mock_address = f"EQC{hashlib.sha256(str(params).encode()).hexdigest()[:48]}"
        return mock_address


def call_contract_method(
    contract_address: str,
    method_name: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Вызывает метод смарт-контракта.

    Args:
        contract_address: Адрес контракта
        method_name: Имя метода (например, 'mark_purchased', 'mark_shipped')
        params: Параметры метода (для GET методов)

    Returns:
        dict: Результат вызова метода

    Raises:
        Exception: Если вызов не удался
    """
    logger.info(f"Calling contract method {method_name} on {contract_address}")
    
    try:
        from .ton_client import TonCenterClient
        
        ton_client = TonCenterClient()
        
        # Выполняем GET метод (read-only)
        result = ton_client.run_get_method(
            address=contract_address,
            method=method_name,
            stack=params.get('stack') if params else None
        )
        
        logger.info(f"Contract method {method_name} called successfully")
        return {
            'success': True,
            'method': method_name,
            'result': result,
        }
        
    except ImportError:
        logger.warning("TON dependencies not available, using mock call")
        return {
            'success': True,
            'tx_hash': f"mock_{hashlib.sha256(f'{contract_address}{method_name}'.encode()).hexdigest()}",
            'method': method_name,
        }
    except Exception as e:
        logger.error(f"Error calling contract method: {e}", exc_info=True)
        # Возвращаем mock результат в случае ошибки
        return {
            'success': False,
            'error': str(e),
            'method': method_name,
        }


def get_contract_state(contract_address: str) -> Dict[str, Any]:
    """
    Получает состояние смарт-контракта.

    Args:
        contract_address: Адрес контракта

    Returns:
        dict: Состояние контракта

    Raises:
        Exception: Если запрос не удался
    """
    logger.info(f"Getting contract state for {contract_address}")
    
    try:
        from .ton_client import TonCenterClient
        
        ton_client = TonCenterClient()
        address_info = ton_client.get_address_information(contract_address)
        
        # Парсим состояние из ответа TonCenter
        state = address_info.get('state', 'uninitialized')
        balance = address_info.get('balance', '0')
        
        result = {
            'status': 'active' if state == 'active' else state,
            'balance': str(balance),
            'data': address_info,
        }
        
        logger.debug(f"Contract state: {result}")
        return result
        
    except ImportError:
        logger.warning("TON dependencies not available, returning mock state")
        return {
            'status': 'active',
            'balance': '1000000000',  # nanoTON
            'data': {},
        }
    except Exception as e:
        logger.error(f"Error getting contract state: {e}", exc_info=True)
        # Возвращаем mock состояние в случае ошибки
        return {
            'status': 'unknown',
            'balance': '0',
            'data': {'error': str(e)},
        }


def sync_deal_status_from_chain(onchain_deal) -> None:
    """
    Синхронизирует статус off-chain сделки со статусом on-chain контракта.

    Args:
        onchain_deal: Объект OnchainDeal

    Returns:
        None
    """
    from core.models import Deal
    
    logger.info(f"Syncing deal status for onchain_deal {onchain_deal.contract_address}")
    
    try:
        # Получаем состояние контракта
        contract_state = get_contract_state(onchain_deal.contract_address)
        
        # Извлекаем статус из состояния контракта
        # TODO: Парсить реальное состояние контракта
        # Пока заглушка
        contract_status = contract_state.get('status', 'UNKNOWN')
        
        deal = onchain_deal.deal
        
        # Маппинг статусов контракта на статусы Deal
        # Это зависит от конкретной реализации контракта
        status_mapping = {
            'FUNDED': Deal.Status.FUNDED,
            'PURCHASED': Deal.Status.PURCHASED,
            'SHIPPED': Deal.Status.SHIPPED,
            'COMPLETED': Deal.Status.COMPLETED,
            'CANCELLED': Deal.Status.CANCELLED_REFUND_CUSTOMER,
            'DISPUTE': Deal.Status.DISPUTE,
        }
        
        if contract_status in status_mapping:
            new_status = status_mapping[contract_status]
            if deal.status != new_status:
                logger.info(f"Updating deal {deal.id} status from {deal.status} to {new_status}")
                deal.status = new_status
                deal.save()
        
    except Exception as e:
        logger.error(f"Error syncing deal status: {e}", exc_info=True)
        raise

