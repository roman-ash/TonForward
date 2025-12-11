"""
Модуль для деплоя контрактов через pytonlib.

Pytonlib - официальная Python библиотека TON, которая правильно работает с state_init.
"""
import os
import logging
from decimal import Decimal
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from pytonlib import TonlibClient
    from pytonlib.utils.wallet import wallets
    from pytonlib.utils.address import prepare_address
    PYTONLIB_AVAILABLE = True
except ImportError:
    PYTONLIB_AVAILABLE = False
    TonlibClient = None
    wallets = None


def deploy_contract_with_pytonlib(
    code_cell,
    init_data_cell,
    amount_ton: Decimal,
    wallet_mnemonic: str,
    seqno: int,
    network: str = "testnet"
) -> Tuple[str, str]:
    """
    Деплоит контракт через pytonlib.
    
    Args:
        code_cell: Cell с кодом контракта
        init_data_cell: Cell с init data
        amount_ton: Сумма для отправки на контракт
        wallet_mnemonic: Mnemonic фраза кошелька (24 слова)
        seqno: Sequence number кошелька (опционально, будет получен автоматически)
        network: Сеть ("testnet" или "mainnet")
        
    Returns:
        Tuple[str, str]: (contract_address, transaction_hash)
    """
    if not PYTONLIB_AVAILABLE:
        raise ImportError(
            "pytonlib is not available. "
            "Install with: pip install pytonlib"
        )
    
    from tonsdk.boc import begin_cell
    from tonsdk.utils import to_nano, bytes_to_b64str
    from core.ton_contracts import calculate_contract_address
    import asyncio
    
    logger.info(f"Deploying contract via pytonlib (network: {network})")
    
    # Вычисляем адрес контракта
    contract_address = calculate_contract_address(code_cell, init_data_cell)
    logger.info(f"Contract address: {contract_address}")
    
    # Создаем state_init
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
    
    # Конвертируем state_init в BOC
    state_init_boc = state_init.to_boc(False)
    state_init_b64 = bytes_to_b64str(state_init_boc)
    
    async def deploy_async():
        # Для pytonlib нужно создать клиент с правильной конфигурацией
        # Это сложно и требует дополнительных настроек
        # Пока возвращаем ошибку о том, что требуется настройка
        raise NotImplementedError(
            "Pytonlib deployment requires additional configuration. "
            "Please use alternative method or configure pytonlib properly. "
            "See: https://github.com/toncenter/pytonlib"
        )
    
    # Запускаем асинхронную функцию
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        contract_addr, tx_hash = loop.run_until_complete(deploy_async())
        return contract_addr, tx_hash
    finally:
        loop.close()


# Альтернативный вариант - использовать pytonlib без async (синхронный wrapper)
def deploy_contract_with_pytonlib_sync(
    code_cell,
    init_data_cell,
    amount_ton: Decimal,
    wallet_mnemonic: str,
    seqno: Optional[int] = None,
    network: str = "testnet"
) -> Tuple[str, str]:
    """
    Синхронная обёртка для deploy_contract_with_pytonlib.
    """
    return deploy_contract_with_pytonlib(
        code_cell=code_cell,
        init_data_cell=init_data_cell,
        amount_ton=amount_ton,
        wallet_mnemonic=wallet_mnemonic,
        seqno=seqno if seqno is not None else -1,
        network=network
    )

