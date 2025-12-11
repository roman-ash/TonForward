"""
Модуль для работы с контрактами TON.

Содержит константы и функции для сборки контрактов Deal.
"""

import os
from typing import Dict, Any
from decimal import Decimal
import logging

try:
    from tonsdk.boc import Cell, begin_cell
    from tonsdk.utils import b64str_to_bytes
    TONSDK_AVAILABLE = True
except ImportError:
    TONSDK_AVAILABLE = False
    Cell = None
    begin_cell = None
    b64str_to_bytes = None

from .ton_utils import convert_ton_to_nano

logger = logging.getLogger(__name__)


# TODO: После компиляции Tact контракта Deal, поместите сюда BOC код контракта в base64
# Это будет результат компиляции, например:
# DEAL_CODE_B64 = "te6cckEBAQEA..."
# Переменная читается из окружения DEAL_CONTRACT_CODE_B64
DEAL_CODE_B64 = os.getenv("DEAL_CONTRACT_CODE_B64", "").strip()

# Для отладки: проверка наличия переменной
if not DEAL_CODE_B64:
    logger.warning("DEAL_CONTRACT_CODE_B64 environment variable is not set")


def load_deal_code_cell() -> Cell:
    """
    Загружает Cell с кодом контракта Deal.
    
    Returns:
        Cell: Cell с кодом контракта
        
    Raises:
        ImportError: Если tonsdk не установлен
        ValueError: Если код контракта не задан или невалиден
    """
    if not TONSDK_AVAILABLE:
        raise ImportError(
            "tonsdk is required for contract operations. "
            "Install it with: pip install tonsdk"
        )
    
    # Перечитываем переменную окружения каждый раз (на случай изменений)
    deal_code_b64 = os.getenv("DEAL_CONTRACT_CODE_B64", "").strip()
    
    if not deal_code_b64:
        raise ValueError(
            "DEAL_CONTRACT_CODE_B64 environment variable is required. "
            "Please compile your Tact contract and set the code BOC in .env file. "
            "After adding it, restart the Docker container with: docker-compose restart web"
        )
    
    try:
        code_bytes = b64str_to_bytes(deal_code_b64)
        code_cell = Cell.one_from_boc(code_bytes)
        logger.info("Deal contract code cell loaded successfully")
        return code_cell
    except Exception as e:
        logger.error(f"Failed to load deal code cell: {e}")
        raise ValueError(
            f"Invalid DEAL_CONTRACT_CODE_B64: {e}. "
            "Please check that the base64 string is correct."
        ) from e


def build_deal_init_data_cell(params: Dict[str, Any]) -> Cell:
    """
    Строит init data cell для контракта Deal.
    
    Структура init data зависит от вашего Tact контракта.
    Пример структуры (нужно адаптировать под ваш контракт):
    
    init(
        customer: Address,
        buyer: Address,
        serviceWallet: Address,
        arbiter: Address,
        itemPriceNano: Int,
        buyerFeeNano: Int,
        serviceFeeNano: Int,
        insuranceNano: Int,
        purchaseDeadline: Int,
        shipDeadline: Int,
        confirmDeadline: Int,
        metadataHash: Slice
    )
    
    Args:
        params: Словарь с параметрами:
            - customer_address: str - адрес заказчика
            - buyer_address: str - адрес байера
            - service_wallet: str - адрес сервисного кошелька
            - arbiter_wallet: str - адрес арбитра
            - item_price_ton: Decimal - цена товара в TON
            - buyer_fee_ton: Decimal - вознаграждение байера в TON
            - shipping_budget_ton: Decimal - бюджет на доставку в TON (опционально, по умолчанию 0)
            - service_fee_ton: Decimal - комиссия сервиса в TON
            - insurance_ton: Decimal - страховка в TON
            - purchase_deadline_ts: int - timestamp дедлайна покупки
            - ship_deadline_ts: int - timestamp дедлайна отправки
            - confirm_deadline_ts: int - timestamp дедлайна подтверждения
            - metadata_hash: bytes - hash метаданных
    
    Returns:
        Cell: Init data cell для контракта
        
    Raises:
        ImportError: Если tonsdk не установлен
        ValueError: Если параметры некорректны
    """
    if not TONSDK_AVAILABLE:
        raise ImportError("tonsdk is required for contract operations")
    
    try:
        from tonsdk.utils import Address
        
        # Парсим адреса
        customer_addr = Address(params['customer_address'])
        buyer_addr = Address(params['buyer_address'])
        service_addr = Address(params['service_wallet'])
        arbiter_addr = Address(params['arbiter_wallet'])
        
        # Конвертируем суммы в nanoTON
        item_price_nano = convert_ton_to_nano(Decimal(str(params['item_price_ton'])))
        buyer_fee_nano = convert_ton_to_nano(Decimal(str(params['buyer_fee_ton'])))
        # shipping_budget_ton может отсутствовать в старых данных, используем 0 по умолчанию
        shipping_budget_nano = convert_ton_to_nano(Decimal(str(params.get('shipping_budget_ton', '0'))))
        service_fee_nano = convert_ton_to_nano(Decimal(str(params['service_fee_ton'])))
        insurance_nano = convert_ton_to_nano(Decimal(str(params['insurance_ton'])))
        
        # Получаем таймстемпы
        purchase_deadline = int(params['purchase_deadline_ts'])
        ship_deadline = int(params['ship_deadline_ts'])
        confirm_deadline = int(params['confirm_deadline_ts'])
        
        # Получаем hash метаданных и конвертируем в uint256
        metadata_hash = params.get('metadata_hash', b'\x00' * 32)
        if isinstance(metadata_hash, str):
            metadata_hash = bytes.fromhex(metadata_hash)
        elif not isinstance(metadata_hash, bytes):
            raise ValueError("metadata_hash must be bytes or hex string")
        
        # Берем первые 32 bytes и конвертируем в int (uint256)
        # Если hash меньше 32 bytes, дополняем нулями
        if len(metadata_hash) < 32:
            metadata_hash = metadata_hash + b'\x00' * (32 - len(metadata_hash))
        elif len(metadata_hash) > 32:
            metadata_hash = metadata_hash[:32]
        
        # Конвертируем bytes в int (big-endian)
        metadata_hash_uint256 = int.from_bytes(metadata_hash, byteorder='big')
        
        # Собираем init data cell
        # Структура точно соответствует тому, как Tact упаковывает данные (см. initDeal_init_args):
        #
        # Основной Cell (b_0):
        #   - storeUint(0, 1) - первый бит (флаг Deployable)
        #   - storeAddress(customer)
        #   - storeAddress(buyer)
        #   - storeAddress(serviceWallet)
        #   - storeRef(b_1) - ссылка на первую часть
        #
        # Первая ссылка (b_1):
        #   - storeAddress(arbiter)
        #   - storeCoins(itemPriceNano)
        #   - storeCoins(buyerFeeNano)
        #   - storeCoins(shippingBudgetNano)
        #   - storeCoins(serviceFeeNano)
        #   - storeCoins(insuranceNano)
        #   - storeUint(purchaseDeadline, 64)
        #   - storeUint(shipDeadline, 64)
        #   - storeRef(b_2) - ссылка на вторую часть
        #
        # Вторая ссылка (b_2):
        #   - storeUint(confirmDeadline, 64)
        #   - storeUint(metadataHash, 256)
        
        # Вторая ссылка (b_2): confirmDeadline + metadataHash
        b_2 = (
            begin_cell()
            .store_uint(confirm_deadline, 64)
            .store_uint(metadata_hash_uint256, 256)
            .end_cell()
        )
        
        # Первая ссылка (b_1): arbiter + все суммы + дедлайны + ссылка на b_2
        b_1 = (
            begin_cell()
            .store_address(arbiter_addr)
            .store_coins(item_price_nano)
            .store_coins(buyer_fee_nano)
            .store_coins(shipping_budget_nano)
            .store_coins(service_fee_nano)
            .store_coins(insurance_nano)
            .store_uint(purchase_deadline, 64)
            .store_uint(ship_deadline, 64)
            .store_ref(b_2)
            .end_cell()
        )
        
        # Основной Cell (b_0): флаг + первые 3 адреса + ссылка на b_1
        init_data = (
            begin_cell()
            .store_uint(0, 1)  # Флаг Deployable (0 = not special)
            .store_address(customer_addr)
            .store_address(buyer_addr)
            .store_address(service_addr)
            .store_ref(b_1)
            .end_cell()
        )
        
        logger.info("Deal init data cell built successfully")
        return init_data
        
    except KeyError as e:
        raise ValueError(f"Missing required parameter: {e}") from e
    except Exception as e:
        logger.error(f"Failed to build deal init data cell: {e}")
        raise ValueError(f"Invalid parameters: {e}") from e


def calculate_contract_address(code_cell: Cell, init_data_cell: Cell, workchain: int = 0) -> str:
    """
    Вычисляет адрес контракта по коду и init data.
    
    Args:
        code_cell: Cell с кодом контракта
        init_data_cell: Cell с init data
        workchain: Workchain (обычно 0 для masterchain)
        
    Returns:
        str: Адрес контракта в формате EQ...
    """
    if not TONSDK_AVAILABLE:
        raise ImportError("tonsdk is required for contract operations")
    
    try:
        from tonsdk.boc import begin_cell
        from tonsdk.utils import Address
        import hashlib
        
        # Собираем state_init согласно структуре TON (как в ton_wallet.py):
        # split_depth: None, special: None, code: Some, data: Some, library: None
        state_init = (
            begin_cell()
            .store_bit(0)  # split_depth = None
            .store_bit(0)  # special = None
            .store_bit(1)  # code = Some
            .store_ref(code_cell)
            .store_bit(1)  # data = Some
            .store_ref(init_data_cell)
            .store_bit(0)  # library = None
            .end_cell()
        )
        
        # Вычисляем hash state_init для адреса контракта
        # В TON адрес контракта вычисляется как hash от state_init
        # Алгоритм: берем state_init, вычисляем hash, создаем адрес
        
        # Получаем hash representation state_init
        state_init_boc = state_init.to_boc(False)  # False = без index
        
        # Вычисляем hash_part (первые 32 байта SHA256)
        hash_part = hashlib.sha256(state_init_boc).digest()
        
        # Создаем адрес: workchain (int) + hash_part (bytes)
        # Address принимает либо строку формата "workchain:hash_hex", либо workchain и hash_part отдельно
        # Попробуем создать через конструктор с workchain и hash_part
        try:
            # Формат: Address(workchain, hash_part_bytes)
            contract_address_obj = Address(workchain, hash_part)
            contract_address = contract_address_obj.to_string(True, True, True)
        except (TypeError, ValueError):
            # Fallback: используем строковый формат
            address_str = f"{workchain}:{hash_part.hex()}"
            contract_address = Address(address_str).to_string(True, True, True)
        
        return contract_address
    except Exception as e:
        logger.error(f"Failed to calculate contract address: {e}", exc_info=True)
        raise

