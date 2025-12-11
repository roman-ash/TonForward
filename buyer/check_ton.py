#!/usr/bin/env python
"""
Простая проверка TON настроек через Django shell.

Использование:
    docker-compose exec web python manage.py shell
    >>> exec(open('check_ton.py').read())
    
Или:
    docker-compose exec web python manage.py shell < check_ton.py
"""

import os
from core.ton_contracts import load_deal_code_cell
from core.ton_client import TonCenterClient
from core.ton_wallet import TonWalletService

print("=" * 60)
print("TON Setup Checker")
print("=" * 60)

# 1. Проверка переменных окружения
print("\n1. Environment Variables:")
print("-" * 60)

toncenter_url = os.getenv('TONCENTER_URL', 'https://toncenter.com/api/v2')
is_testnet = 'testnet' in toncenter_url.lower()

print(f"  TONCENTER_URL: {toncenter_url}")
print(f"  Network: {'TESTNET' if is_testnet else 'MAINNET'}")

# 2. Проверка контракта
print("\n2. Deal Contract:")
print("-" * 60)

try:
    code_cell = load_deal_code_cell()
    print(f"  ✓ Contract code loaded")
    # Получаем hash из Cell
    try:
        if hasattr(code_cell, 'hash'):
            cell_hash = code_cell.hash.hex()[:16] if hasattr(code_cell.hash, 'hex') else str(code_cell.hash)[:16]
        elif hasattr(code_cell, 'bytes_hash'):
            cell_hash = code_cell.bytes_hash().hex()[:16]
        else:
            # Вычисляем hash через serialize
            import hashlib
            cell_bytes = code_cell.serialize()
            cell_hash = hashlib.sha256(cell_bytes).hexdigest()[:16]
        print(f"    Code cell hash: {cell_hash}...")
    except Exception as hash_error:
        print(f"    Code cell loaded (could not get hash: {hash_error})")
except Exception as e:
    print(f"  ✗ Error loading contract: {e}")
    exit(1)

# 3. Проверка TonCenter клиента
print("\n3. TonCenter Client:")
print("-" * 60)

try:
    client = TonCenterClient()
    print(f"  ✓ TonCenter client initialized")
    print(f"    Base URL: {client.base_url}")
except Exception as e:
    print(f"  ✗ Error initializing client: {e}")
    exit(1)

# 4. Проверка кошельков
print("\n4. Wallets:")
print("-" * 60)

mnemonic = os.getenv('TON_MNEMONIC')
if not mnemonic:
    print("  ✗ TON_MNEMONIC not set")
    exit(1)

try:
    wallet = TonWalletService(mnemonic=mnemonic, ton_client=client)
    print(f"  ✓ Service wallet initialized")
    print(f"    Address: {wallet.address}")
    
    # Проверка баланса
    info = client.get_address_information(wallet.address)
    balance_nano = int(info.get('balance', 0))
    balance_ton = balance_nano / 1e9
    state = info.get('state', 'unknown')
    
    print(f"    Balance: {balance_ton:.2f} TON ({balance_nano} nanoTON)")
    print(f"    State: {state}")
    
    if is_testnet:
        if balance_ton < 1.0:
            print(f"    ⚠️  Low balance for testnet! Get testnet TON from faucet:")
            print(f"        https://t.me/testgiver_ton_bot")
        else:
            print(f"    ✓ Sufficient balance for testing")
except Exception as e:
    print(f"  ✗ Error initializing wallet: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "=" * 60)
print("✓ Setup looks good! Ready for testing.")
print("=" * 60)

