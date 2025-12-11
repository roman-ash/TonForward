#!/usr/bin/env python
"""
Скрипт для проверки настройки TON (testnet/mainnet).

Использование:
    docker-compose exec web python test_ton_setup.py
"""

import os
import sys
import django

# Настройка Django
# В контейнере рабочая директория уже /app/src (это папка buyer)
# Просто устанавливаем settings модуль - Django сам найдет нужные пути
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'buyer.settings')
django.setup()

def check_ton_setup():
    """Проверяет настройку TON для тестирования."""
    
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
    
    if is_testnet:
        print("  ✓ Using testnet (correct for testing)")
    else:
        print("  ⚠️  Using mainnet (use testnet for testing!)")
        print("     Set TONCENTER_URL=https://testnet.toncenter.com/api/v2 in .env")
    
    toncenter_api_key = os.getenv('TONCENTER_API_KEY', '')
    if toncenter_api_key:
        print(f"  TONCENTER_API_KEY: {toncenter_api_key[:10]}... (set)")
    else:
        print("  TONCENTER_API_KEY: (not set - optional, but recommended)")
    
    mnemonic = os.getenv('TON_MNEMONIC', '')
    service_wallet = os.getenv('TON_SERVICE_WALLET', '')
    arbiter_wallet = os.getenv('TON_ARBITER_WALLET', '')
    
    print(f"  TON_MNEMONIC: {'✓ (set)' if mnemonic else '✗ (not set)'}")
    print(f"  TON_SERVICE_WALLET: {service_wallet if service_wallet else '✗ (not set)'}")
    print(f"  TON_ARBITER_WALLET: {arbiter_wallet if arbiter_wallet else '✗ (not set)'}")
    
    # 2. Проверка контракта
    print("\n2. Deal Contract:")
    print("-" * 60)
    
    try:
        from core.ton_contracts import load_deal_code_cell
        code_cell = load_deal_code_cell()
        print(f"  ✓ Contract code loaded")
        
        # Получаем hash из Cell через to_boc (как в ton_wallet.py)
        try:
            from tonsdk.utils import bytes_to_b64str
            cell_boc = code_cell.to_boc(False)  # False = без index
            import hashlib
            cell_hash = hashlib.sha256(cell_boc).hexdigest()[:16]
            print(f"    Code cell hash: {cell_hash}...")
            print(f"    Code cell size: {len(cell_boc)} bytes")
        except Exception as hash_error:
            print(f"    Code cell loaded (could not compute hash: {hash_error})")
            print(f"    Cell type: {type(code_cell)}")
    except Exception as e:
        print(f"  ✗ Error loading contract: {e}")
        print("    Make sure DEAL_CONTRACT_CODE_B64 is set in .env")
        return False
    
    # 3. Проверка TonCenter клиента
    print("\n3. TonCenter Client:")
    print("-" * 60)
    
    try:
        from core.ton_client import TonCenterClient
        client = TonCenterClient()
        print(f"  ✓ TonCenter client initialized")
        print(f"    Base URL: {client.base_url}")
        
        # Попытка проверить доступность API (простой запрос)
        try:
            # Пробуем получить информацию о нулевом адресе (это не должно работать, но покажет доступность API)
            test_address = "EQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAM9c"
            try:
                info = client.get_address_information(test_address)
                print(f"  ✓ API is accessible")
            except Exception as api_error:
                # Ошибка ожидаема, но значит API доступен
                error_msg = str(api_error).lower()
                if 'http' not in error_msg or 'timeout' not in error_msg:
                    print(f"  ✓ API is accessible (error is expected for test address)")
                else:
                    print(f"  ⚠️  API might be unreachable: {api_error}")
        except Exception as e:
            print(f"  ⚠️  Could not test API connectivity: {e}")
            
    except Exception as e:
        print(f"  ✗ Error initializing client: {e}")
        return False
    
    # 4. Проверка кошельков
    print("\n4. Wallets:")
    print("-" * 60)
    
    if not mnemonic:
        print("  ⚠️  TON_MNEMONIC not set - cannot check wallets")
        return False
    
    try:
        from core.ton_wallet import TonWalletService
        
        wallet = TonWalletService(mnemonic=mnemonic, ton_client=client)
        print(f"  ✓ Service wallet initialized")
        print(f"    Address: {wallet.address}")
        
        # Проверка баланса
        try:
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
                    print(f"        https://t.me/faucet_test_ton_bot")
                else:
                    print(f"    ✓ Sufficient balance for testing")
            else:
                if balance_ton < 0.1:
                    print(f"    ⚠️  Very low balance! Make sure you have enough TON")
        except Exception as e:
            print(f"    ⚠️  Could not get balance: {e}")
            
        # Проверка соответствия адреса
        if service_wallet and wallet.address != service_wallet:
            print(f"    ⚠️  WARNING: Wallet address from mnemonic differs from TON_SERVICE_WALLET!")
            print(f"        Mnemonic address: {wallet.address}")
            print(f"        Env address:      {service_wallet}")
        
    except Exception as e:
        print(f"  ✗ Error initializing wallet: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 5. Проверка arbiter кошелька
    if arbiter_wallet:
        try:
            info = client.get_address_information(arbiter_wallet)
            balance_nano = int(info.get('balance', 0))
            balance_ton = balance_nano / 1e9
            print(f"\n  ✓ Arbiter wallet checked")
            print(f"    Address: {arbiter_wallet}")
            print(f"    Balance: {balance_ton:.2f} TON")
        except Exception as e:
            print(f"\n  ⚠️  Could not check arbiter wallet: {e}")
    else:
        print("\n  ⚠️  TON_ARBITER_WALLET not set")
    
    # Итоговая проверка
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    
    all_ok = (
        code_cell is not None and
        client is not None and
        wallet is not None and
        (not is_testnet or balance_ton >= 0.1)
    )
    
    if all_ok:
        print("✓ Setup looks good! Ready for testing.")
        if is_testnet:
            print("\nNext steps:")
            print("1. Test contract deployment through API")
            print("2. Monitor Celery logs for deployment status")
            print("3. Check deployed contracts on testnet explorer:")
            print("   https://testnet.tonscan.org/")
    else:
        print("⚠️  Setup incomplete. Please fix the issues above.")
        if not is_testnet:
            print("\n⚠️  WARNING: You are using MAINNET!")
            print("   For testing, set TONCENTER_URL=https://testnet.toncenter.com/api/v2")
    
    return all_ok

if __name__ == '__main__':
    try:
        success = check_ton_setup()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

