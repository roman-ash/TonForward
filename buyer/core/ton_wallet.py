"""
Сервис для работы с TON кошельком.

Модуль для управления сервисным кошельком, подписи и отправки транзакций.
"""

import os
from typing import Optional, Dict
from decimal import Decimal
import logging

try:
    from tonsdk.contract.wallet import Wallets, WalletVersionEnum
    from tonsdk.utils import to_nano, bytes_to_b64str, b64str_to_bytes
    from tonsdk.boc import Cell
    TONSDK_AVAILABLE = True
except ImportError:
    TONSDK_AVAILABLE = False
    Wallets = None
    WalletVersionEnum = None
    to_nano = None
    bytes_to_b64str = None
    b64str_to_bytes = None
    Cell = None

from .ton_client import TonCenterClient

logger = logging.getLogger(__name__)


class TonWalletService:
    """
    Сервис для работы с TON кошельком.
    
    Управляет сервисным кошельком, подписывает и отправляет транзакции.
    """
    
    def __init__(
        self,
        mnemonic: Optional[str] = None,
        ton_client: Optional[TonCenterClient] = None,
        wallet_version: str = "v4r2"
    ):
        """
        Инициализирует сервис кошелька.
        
        Args:
            mnemonic: Mnemonic фраза кошелька (24 слова) или None для получения из TON_MNEMONIC
            ton_client: Клиент TonCenter (создается автоматически если не передан)
            wallet_version: Версия кошелька (v3r2, v4r2 и т.д.)
            
        Raises:
            ImportError: Если tonsdk не установлен
            ValueError: Если mnemonic не предоставлен
        """
        if not TONSDK_AVAILABLE:
            raise ImportError(
                "tonsdk is required for TonWalletService. "
                "Install it with: pip install tonsdk"
            )
        
        self.mnemonic = mnemonic or os.getenv("TON_MNEMONIC")
        if not self.mnemonic:
            raise ValueError(
                "TON_MNEMONIC environment variable or mnemonic parameter is required"
            )
        
        self.ton_client = ton_client or TonCenterClient()
        
        # Определяем версию кошелька
        wallet_version_map = {
            "v3r2": WalletVersionEnum.v3r2,
            "v4r2": WalletVersionEnum.v4r2,
        }
        wallet_enum = wallet_version_map.get(wallet_version, WalletVersionEnum.v4r2)
        
        # Создаем кошелек из mnemonic
        mnemonic_words = self.mnemonic.split()
        if len(mnemonic_words) != 24:
            raise ValueError(
                f"Invalid mnemonic: expected 24 words, got {len(mnemonic_words)}"
            )
        
        self.wallet = Wallets.from_mnemonic(
            mnemonic=mnemonic_words,
            wallet_version=wallet_enum,
            workchain=0,
        )
        
        self.address = self.wallet.address.to_string(True, True, True)
        
        logger.info(f"TonWalletService initialized: address={self.address}")
    
    def get_seqno(self) -> int:
        """
        Получает текущий seqno кошелька из блокчейна.
        
        Returns:
            int: Текущий seqno кошелька
        """
        return self.ton_client.get_wallet_seqno(self.address)
    
    def deploy_contract(
        self,
        code_cell: Cell,
        init_data_cell: Cell,
        amount_ton: Decimal,
        comment: Optional[str] = None
    ) -> str:
        """
        Деплоит контракт с заданным кодом и init data.
        
        Args:
            code_cell: Cell с кодом контракта
            init_data_cell: Cell с init data контракта
            amount_ton: Сумма в TON для отправки на контракт (escrow)
            comment: Комментарий к транзакции (опционально)
            
        Returns:
            str: Адрес деплоенного контракта
            
        Raises:
            Exception: Если деплой не удался
        """
        from tonsdk.boc import begin_cell
        
        logger.info(f"Deploying contract with amount {amount_ton} TON")
        
        # Собираем state_init
        state_init = begin_cell()\
            .store_bit(0)  # is_not_special
            .store_ref(code_cell)\
            .store_ref(init_data_cell)\
            .end_cell()
        
        # Вычисляем адрес контракта
        contract_address_cell = self.wallet.address.generate_state_init_address(
            code_cell, init_data_cell
        )
        contract_address = contract_address_cell.to_string(True, True, True)
        
        logger.info(f"Contract address: {contract_address}")
        
        # Получаем seqno кошелька
        seqno = self.get_seqno()
        logger.debug(f"Wallet seqno: {seqno}")
        
        # Подготавливаем payload если есть comment
        payload = None
        if comment:
            payload = begin_cell().store_uint(0, 32).store_string(comment).end_cell()
        
        # Создаем транзакцию от кошелька
        query = self.wallet.create_transfer_message(
            to_addr=contract_address,
            amount=to_nano(float(amount_ton), "ton"),
            seqno=seqno,
            state_init=state_init,
            payload=payload,
            send_mode=3,  # отправляем все и уничтожаем контракт если нужно
        )
        
        # Получаем BOC транзакции
        boc = query["message"].to_boc(False)
        boc_b64 = bytes_to_b64str(boc)
        
        logger.info("Sending deploy transaction to TON network")
        
        # Отправляем через TonCenter
        try:
            result = self.ton_client.send_boc(boc_b64)
            logger.info(f"Deploy transaction sent successfully: {result}")
        except Exception as e:
            logger.error(f"Failed to send deploy transaction: {e}")
            raise
        
        return contract_address
    
    def send_transfer(
        self,
        to_address: str,
        amount_ton: Decimal,
        comment: Optional[str] = None,
        payload: Optional[Cell] = None
    ) -> Dict:
        """
        Отправляет TON с кошелька на указанный адрес.
        
        Args:
            to_address: Адрес получателя
            amount_ton: Сумма в TON
            comment: Комментарий к транзакции (создается payload автоматически)
            payload: Кастомный payload (если не указан comment)
            
        Returns:
            dict: Результат отправки
        """
        from tonsdk.boc import begin_cell
        
        logger.info(f"Sending {amount_ton} TON to {to_address}")
        
        seqno = self.get_seqno()
        
        # Создаем payload
        if payload is None and comment:
            payload = begin_cell().store_uint(0, 32).store_string(comment).end_cell()
        
        query = self.wallet.create_transfer_message(
            to_addr=to_address,
            amount=to_nano(float(amount_ton), "ton"),
            seqno=seqno,
            payload=payload,
            send_mode=3,
        )
        
        boc = query["message"].to_boc(False)
        boc_b64 = bytes_to_b64str(boc)
        
        result = self.ton_client.send_boc(boc_b64)
        logger.info(f"Transfer sent successfully: {result}")
        
        return result

