"""
Модуль для деплоя контрактов с правильным state_init.

Использует ручное создание сообщения через tonsdk для гарантированного включения state_init.
"""
import os
import logging
from decimal import Decimal
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def deploy_contract_with_manual_state_init(
    code_cell,
    init_data_cell,
    amount_ton: Decimal,
    wallet_mnemonic: str,
    seqno: Optional[int] = None,
    network: str = "testnet"
) -> Tuple[str, str]:
    """
    Деплоит контракт с правильным включением state_init.
    
    Создает сообщение вручную через tonsdk, гарантируя включение state_init.
    
    Args:
        code_cell: Cell с кодом контракта
        init_data_cell: Cell с init data
        amount_ton: Сумма для отправки на контракт
        wallet_mnemonic: Mnemonic фраза кошелька (24 слова)
        seqno: Sequence number кошелька (опционально)
        network: Сеть ("testnet" или "mainnet")
        
    Returns:
        Tuple[str, str]: (contract_address, transaction_hash)
    """
    from tonsdk.boc import begin_cell
    from tonsdk.utils import to_nano, bytes_to_b64str, Address as TonAddress
    from core.ton_contracts import calculate_contract_address
    from core.ton_client import TonCenterClient
    from tonsdk.contract.wallet import Wallets, WalletVersionEnum
    import hashlib
    import nacl.signing
    import nacl.encoding
    from mnemonic import Mnemonic
    
    logger.info(f"Deploying contract with manual state_init (network: {network})")
    
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
    
    # Получаем кошелек из mnemonic через tonsdk
    mnemonic_words = wallet_mnemonic.split()
    wallet_result = Wallets.from_mnemonics(
        mnemonics=mnemonic_words,
        wallet_version=WalletVersionEnum.v3r2,
        workchain=0
    )
    
    # Извлекаем wallet объект
    wallet = None
    if isinstance(wallet_result, tuple):
        for item in wallet_result:
            if hasattr(item, 'address'):
                wallet = item
                break
        if wallet is None and len(wallet_result) > 0:
            wallet = wallet_result[0]
    elif isinstance(wallet_result, list):
        for item in wallet_result:
            if hasattr(item, 'address'):
                wallet = item
                break
        if wallet is None and len(wallet_result) > 0:
            wallet = wallet_result[0]
    else:
        wallet = wallet_result
    
    if wallet is None or not hasattr(wallet, 'address'):
        raise ValueError(f"Could not extract wallet object. Type: {type(wallet_result)}")
    
    # Получаем seqno если не указан
    if seqno is None or seqno < 0:
        try:
            ton_client = TonCenterClient()
            wallet_address = wallet.address.to_string(True, True, True)
            seqno = ton_client.get_wallet_seqno(wallet_address)
            if seqno == 0:
                logger.warning("Got seqno=0, using provided seqno or 0")
                seqno = 0
        except Exception as e:
            logger.warning(f"Could not get seqno automatically: {e}, using seqno=0")
            seqno = 0
    
    # Конвертируем amount в nanoTON
    amount_nano = int(to_nano(float(amount_ton), "ton"))
    
    # Создаем внутреннее сообщение с state_init вручную
    # tonsdk create_transfer_message НЕ включает state_init правильно
    wallet_addr = TonAddress(wallet.address)
    contract_addr = TonAddress(contract_address)
    
    # Создаем внутреннее сообщение с state_init
    internal_message = (
        begin_cell()
        .store_uint(0, 1)  # ihr_disabled = 0
        .store_uint(1, 1)  # bounce = 1
        .store_uint(0, 1)  # bounced = 0
        .store_address(wallet_addr)  # src
        .store_address(contract_addr)  # dst
        .store_coins(amount_nano)  # value
        .store_bit(0)  # extra_currencies = None
        .store_bit(1)  # init = Some
        .store_ref(state_init)  # state_init
        .store_bit(0)  # body = None
        .end_cell()
    )
    
    # Создаем signing message для v3r2
    subwallet_id = 698983191  # стандартный для v3r2
    valid_until = 4294967295
    
    signing_message = (
        begin_cell()
        .store_uint(subwallet_id, 32)
        .store_uint(valid_until, 32)
        .store_uint(seqno, 32)
        .store_uint(0, 8)  # op = 0
        .store_uint(0, 64)  # query_id = 0
        .store_ref(internal_message)
        .end_cell()
    )
    
    # Получаем приватный ключ для подписи
    mnemo = Mnemonic("english")
    seed = mnemo.to_seed(wallet_mnemonic, passphrase="")
    private_key = seed[:32]
    
    # Подписываем сообщение
    signing_message_boc = signing_message.to_boc(False)
    message_hash = hashlib.sha256(signing_message_boc).digest()
    signing_key = nacl.signing.SigningKey(private_key, encoder=nacl.encoding.RawEncoder)
    signed = signing_key.sign(message_hash, encoder=nacl.encoding.RawEncoder)
    signature = signed.signature  # 64 bytes
    
    # Создаем внешнее сообщение с подписью
    external_message = (
        begin_cell()
        .store_bytes(signature)
        .store_ref(signing_message)
        .end_cell()
    )
    
    boc_b64 = bytes_to_b64str(external_message.to_boc(False))
    
    # Отправляем через TonCenter API
    ton_client = TonCenterClient()
    result = ton_client.send_boc(boc_b64)
    
    logger.info(f"Deploy transaction sent via TonCenter (manual state_init): {result}")
    
    # Получаем hash из результата
    # TonCenter возвращает {'@type': 'ok'} при успехе
    tx_hash = "sent"  # Hash будет доступен после обработки транзакции
    
    return contract_address, tx_hash
