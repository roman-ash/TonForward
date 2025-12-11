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
        wallet_version: Optional[str] = None
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
        
        # Определяем версию кошелька (из ENV или параметра, по умолчанию v3r2)
        if wallet_version is None:
            wallet_version = os.getenv("TON_WALLET_VERSION", "v3r2")
        
        wallet_version_map = {
            "v3r2": WalletVersionEnum.v3r2,
            "v4r2": WalletVersionEnum.v4r2,
        }
        wallet_enum = wallet_version_map.get(wallet_version, WalletVersionEnum.v3r2)  # По умолчанию v3r2
        
        # Создаем кошелек из mnemonic
        mnemonic_words = self.mnemonic.split()
        if len(mnemonic_words) != 24:
            raise ValueError(
                f"Invalid mnemonic: expected 24 words, got {len(mnemonic_words)}"
            )
        
        # Используем from_mnemonics (множественное число) - это правильный метод в tonsdk
        try:
            wallet_result = Wallets.from_mnemonics(
                mnemonics=mnemonic_words,
                wallet_version=wallet_enum,
                workchain=0,
            )
            
            # Обрабатываем результат - может быть кортеж или объект
            if isinstance(wallet_result, tuple):
                # Если кортеж, ищем элемент с атрибутом 'address' (это и есть wallet объект)
                wallet = None
                for item in wallet_result:
                    if hasattr(item, 'address'):
                        wallet = item
                        break
                
                # Если не нашли в кортеже, пробуем первый элемент
                if wallet is None and len(wallet_result) > 0:
                    first_item = wallet_result[0]
                    if isinstance(first_item, (list, tuple)) and len(first_item) > 0:
                        wallet = first_item[0]
                    else:
                        wallet = first_item
                
                if wallet is None or not hasattr(wallet, 'address'):
                    raise ValueError(
                        f"Could not find wallet object with 'address' attribute. "
                        f"Result type: {type(wallet_result)}, "
                        f"Result length: {len(wallet_result)}"
                    )
                
                self.wallet = wallet
            else:
                self.wallet = wallet_result
                
        except AttributeError:
            # Fallback для старых версий tonsdk
            if hasattr(Wallets, 'from_mnemonic'):
                wallet_result = Wallets.from_mnemonic(
                    mnemonic=mnemonic_words,
                    wallet_version=wallet_enum,
                    workchain=0,
                )
                # Обрабатываем результат (может быть тоже кортеж)
                if isinstance(wallet_result, tuple):
                    wallet = None
                    for item in wallet_result:
                        if hasattr(item, 'address'):
                            wallet = item
                            break
                    self.wallet = wallet if wallet else wallet_result[0]
                else:
                    self.wallet = wallet_result
            else:
                raise ValueError(
                    f"Wallets class does not have from_mnemonics or from_mnemonic method. "
                    f"Available methods: {[m for m in dir(Wallets) if 'mne' in m.lower() and not m.startswith('_')]}"
                )
        
        # Проверяем, что wallet имеет атрибут address
        if not hasattr(self.wallet, 'address'):
            raise ValueError(
                f"Wallet object missing 'address' attribute. "
                f"Type: {type(self.wallet)}"
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
        comment: Optional[str] = None,
        use_manual_state_init: bool = True
    ) -> str:
        """
        Деплоит контракт с заданным кодом и init data.
        
        Args:
            code_cell: Cell с кодом контракта
            init_data_cell: Cell с init data контракта
            amount_ton: Сумма в TON для отправки на контракт (escrow)
            comment: Комментарий к транзакции (опционально)
            use_manual_state_init: Использовать ручное создание сообщения с state_init (по умолчанию True)
            
        Returns:
            str: Адрес деплоенного контракта
            
        Raises:
            Exception: Если деплой не удался
        """
        from tonsdk.boc import begin_cell
        
        logger.info(f"Deploying contract with amount {amount_ton} TON")
        
        # Собираем state_init согласно структуре TON:
        # StateInit {
        #   split_depth: Maybe (## 5)
        #   special: Maybe TickTock
        #   code: Maybe ^Cell
        #   data: Maybe ^Cell
        #   library: Maybe ^Cell
        # }
        # Формат: split_depth(1 bit) + special(1 bit) + code(1 bit + ref) + data(1 bit + ref) + library(1 bit)
        state_init = (
            begin_cell()
            .store_bit(0)  # split_depth = None (0 = отсутствует)
            .store_bit(0)  # special = None (0 = отсутствует)
            .store_bit(1)  # code = Some (1 = присутствует)
            .store_ref(code_cell)
            .store_bit(1)  # data = Some (1 = присутствует)
            .store_ref(init_data_cell)
            .store_bit(0)  # library = None (0 = отсутствует)
            .end_cell()
        )
        
        # Вычисляем адрес контракта
        from core.ton_contracts import calculate_contract_address
        contract_address = calculate_contract_address(code_cell, init_data_cell)
        
        logger.info(f"Contract address: {contract_address}")
        
        # Получаем seqno кошелька
        seqno = self.get_seqno()
        logger.debug(f"Wallet seqno: {seqno}")
        
        # Проверяем статус кошелька
        try:
            addr_info = self.ton_client.get_address_information(self.address)
            wallet_state = addr_info.get("state", "")
            logger.debug(f"Wallet state: {wallet_state}")
        except Exception as e:
            logger.warning(f"Could not get wallet state: {e}")
            wallet_state = "unknown"
        
        # Если seqno=0 и кошелек active, возможно метод seqno недоступен
        # В этом случае кошелек все равно может работать, но нужно проверить баланс
        if seqno == 0 and wallet_state == "active":
            logger.warning(
                f"Seqno=0 but wallet is active. "
                f"This might be an issue with get_seqno method. "
                f"Trying to proceed with seqno=0..."
            )
        
        # Для деплоя нового контракта через кошелек v3r2 используем create_transfer_message
        # но с правильными параметрами для v3r2
        
        # Для деплоя отправляем достаточную сумму для активации контракта
        # Минимум ~0.1 TON для газа и комиссий, но лучше 0.2-0.3 TON для надежности
        # Основную сумму escrow нужно отправить отдельной транзакцией после деплоя
        deploy_amount_ton = min(amount_ton, Decimal('0.2'))  # Увеличено до 0.2 TON для надежной активации
        deploy_amount_nano = to_nano(float(deploy_amount_ton), "ton")
        
        # Для v3r2 кошелька при деплое контракта нужно использовать правильный формат
        # Попробуем без state_init в transfer message, а создадим внешнее сообщение отдельно
        # Но сначала попробуем стандартный метод с правильным send_mode
        
        # Для деплоя нового контракта используем send_mode=3 (pay fees separately)
        # или send_mode=128 (external message)
        # Но create_transfer_message создает внутреннее сообщение, поэтому используем send_mode=1
        
        logger.info(f"Creating transfer message for contract deployment (seqno={seqno}, amount={deploy_amount_ton} TON)")
        
        if use_manual_state_init:
            # Используем tonutils-py для деплоя с гарантированным state_init
            logger.info("Using tonutils-py deployment method (guaranteed state_init)")
            try:
                from core.ton_deploy_tonutils import deploy_contract_with_manual_state_init
                
                # Определяем network из URL
                network = "testnet" if "testnet" in self.ton_client.base_url.lower() else "mainnet"
                
                contract_addr, tx_hash = deploy_contract_with_manual_state_init(
                    code_cell=code_cell,
                    init_data_cell=init_data_cell,
                    amount_ton=deploy_amount_ton,
                    wallet_mnemonic=self.mnemonic,
                    seqno=seqno,
                    network=network
                )
                logger.info(f"Contract deployed successfully via tonutils-py: {contract_addr}, tx: {tx_hash}")
                return contract_addr
            except ImportError as e:
                logger.warning(f"Manual state_init deployment method not available: {e}, falling back to tonsdk")
                use_manual_state_init = False
            except Exception as e:
                logger.error(f"Manual state_init deployment failed: {e}, falling back to tonsdk")
                logger.exception(e)
                use_manual_state_init = False
        
        if not use_manual_state_init:
            # Fallback: используем стандартный метод (может не включать state_init)
            logger.warning("Using tonsdk create_transfer_message (state_init may not be included)")
            # Используем send_mode=3 (как в успешной транзакции из TONScan)
            # send_mode=3 означает отправку всех оставшихся TON
            query = self.wallet.create_transfer_message(
                to_addr=contract_address,
                amount=deploy_amount_nano,
                seqno=seqno,
                state_init=state_init,
                payload=None,  # Без payload для деплоя нового контракта
                send_mode=3,  # send_mode=3: отправка всех оставшихся TON (как в успешных транзакциях)
            )
            
            # Получаем BOC транзакции
            boc = query["message"].to_boc(False)
            boc_b64 = bytes_to_b64str(boc)
            
            logger.info(f"Sending deploy transaction to TON network")
            logger.debug(f"BOC length: {len(boc)} bytes, BOC base64 length: {len(boc_b64)} chars")
            logger.debug(f"BOC base64 (first 100 chars): {boc_b64[:100]}...")
            
            # Отправляем через TonCenter
            try:
                result = self.ton_client.send_boc(boc_b64)
                logger.info(f"Deploy transaction sent successfully: {result}")
            except Exception as e:
                logger.error(f"Failed to send deploy transaction: {e}")
                logger.error(f"BOC that failed: {boc_b64[:200]}...")
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

