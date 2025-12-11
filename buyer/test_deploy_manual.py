#!/usr/bin/env python3
"""
Скрипт для ручного тестирования деплоя контракта Deal.
Использует tonsdk для создания внешнего сообщения напрямую.
"""
import os
import sys
import django
from decimal import Decimal
import hashlib
import subprocess

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'buyer.settings')
django.setup()

from core.ton_contracts import load_deal_code_cell, build_deal_init_data_cell, calculate_contract_address
from core.ton_utils import convert_ton_to_nano
from tonsdk.contract.wallet import Wallets, WalletVersionEnum
from tonsdk.utils import to_nano, bytes_to_b64str
from tonsdk.boc import begin_cell
from tonsdk.utils import Address

def test_manual_deploy():
    """Тестирует создание внешнего сообщения для деплоя контракта."""
    
    print("=" * 70)
    print("  Manual Contract Deploy Test")
    print("=" * 70)
    
    # Получаем mnemonic
    mnemonic = os.getenv("TON_MNEMONIC")
    if not mnemonic:
        print("❌ TON_MNEMONIC not set in environment")
        return
    
    mnemonic_words = mnemonic.split()
    if len(mnemonic_words) != 24:
        print(f"❌ Invalid mnemonic: expected 24 words, got {len(mnemonic_words)}")
        return
    
    print(f"✓ Mnemonic loaded ({len(mnemonic_words)} words)")
    
    # Создаем кошелек
    try:
        wallet_result = Wallets.from_mnemonics(
            mnemonics=mnemonic_words,
            wallet_version=WalletVersionEnum.v3r2,
            workchain=0
        )
        
        # Обрабатываем результат - может быть кортеж, список или объект
        if isinstance(wallet_result, (tuple, list)):
            # Ищем элемент с атрибутом 'address' (это и есть wallet объект)
            wallet = None
            for item in wallet_result:
                if hasattr(item, 'address'):
                    wallet = item
                    break
            
            # Если не нашли, пробуем первый элемент
            if wallet is None and len(wallet_result) > 0:
                first_item = wallet_result[0]
                if isinstance(first_item, (list, tuple)) and len(first_item) > 0:
                    wallet = first_item[0]
                else:
                    wallet = first_item
        else:
            wallet = wallet_result
        
        if wallet is None or not hasattr(wallet, 'address'):
            print(f"❌ Could not extract wallet from result: {type(wallet_result)}")
            if isinstance(wallet_result, (tuple, list)):
                print(f"   Result length: {len(wallet_result)}")
                print(f"   First item type: {type(wallet_result[0]) if len(wallet_result) > 0 else 'N/A'}")
            return
        
        wallet_address_str = wallet.address.to_string(True, True, True)
        print(f"✓ Wallet created: {wallet_address_str}")
        
        # Проверяем subwallet_id кошелька (для v3r2 должен быть 698983191)
        if hasattr(wallet, 'subwallet_id'):
            print(f"✓ Wallet subwallet_id: {wallet.subwallet_id}")
        else:
            print(f"⚠️  Wallet does not have subwallet_id attribute")
            # Для v3r2 кошелька subwallet_id обычно 698983191
            print(f"   (v3r2 wallets typically use subwallet_id=698983191)")
    except Exception as e:
        print(f"❌ Error creating wallet: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Получаем приватный ключ из mnemonic напрямую
    try:
        # Используем библиотеку mnemonic для получения seed
        try:
            from mnemonic import Mnemonic
            mnemo = Mnemonic("english")
            seed = mnemo.to_seed(mnemonic, passphrase="")
            # Первые 32 байта seed - это приватный ключ для TON
            private_key = seed[:32]
            print("✓ Private key extracted from mnemonic using mnemonic library")
        except ImportError:
            print("⚠️  mnemonic library not available")
            print("   Installing mnemonic library...")
            # Пробуем установить библиотеку через pip
            import subprocess
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "mnemonic", "-q"])
                from mnemonic import Mnemonic
                mnemo = Mnemonic("english")
                seed = mnemo.to_seed(mnemonic, passphrase="")
                private_key = seed[:32]
                print("✓ Private key extracted from mnemonic (after installing library)")
            except Exception as install_error:
                print(f"⚠️  Could not install mnemonic library: {install_error}")
                private_key = None
        
        if not private_key:
            print("⚠️  Will try to use wallet methods instead of manual signing")
            private_key = None
    except Exception as e:
        print(f"⚠️  Error extracting private key: {e}, will use wallet methods")
        import traceback
        traceback.print_exc()
        private_key = None
    
    # Загружаем код контракта
    try:
        code_cell = load_deal_code_cell()
        print("✓ Contract code loaded")
    except Exception as e:
        print(f"❌ Error loading contract code: {e}")
        return
    
    # Создаем тестовые параметры для init_data
    from core.ton_utils import DealOnchainParams
    
    # Тестовые параметры (минимальные значения)
    params = DealOnchainParams(
        customer_address="EQDtw5uP3QDaC_9F6H0f-gAdrjs_jp0bzbw5PyRzn9vW7mN6",
        buyer_address="EQDtw5uP3QDaC_9F6H0f-gAdrjs_jp0bzbw5PyRzn9vW7mN6",
        service_wallet="EQDtw5uP3QDaC_9F6H0f-gAdrjs_jp0bzbw5PyRzn9vW7mN6",
        arbiter_wallet="EQDtw5uP3QDaC_9F6H0f-gAdrjs_jp0bzbw5PyRzn9vW7mN6",
        item_price_nano=convert_ton_to_nano(Decimal('0.1')),
        buyer_fee_nano=convert_ton_to_nano(Decimal('0.02')),
        shipping_budget_nano=convert_ton_to_nano(Decimal('0')),
        service_fee_nano=convert_ton_to_nano(Decimal('0.03')),
        insurance_nano=convert_ton_to_nano(Decimal('0.01')),
        purchase_deadline_ts=1734057600,
        ship_deadline_ts=1734144000,
        confirm_deadline_ts=1734230400,
        metadata_hash_cell=hashlib.sha256(b"test").digest()
    )
    
    # Создаем init_data_cell
    try:
        init_params = {
            'customer_address': params.customer_address,
            'buyer_address': params.buyer_address,
            'service_wallet': params.service_wallet,
            'arbiter_wallet': params.arbiter_wallet,
            'item_price_ton': Decimal(params.item_price_nano) / Decimal('1000000000'),
            'buyer_fee_ton': Decimal(params.buyer_fee_nano) / Decimal('1000000000'),
            'shipping_budget_ton': Decimal(params.shipping_budget_nano) / Decimal('1000000000'),
            'service_fee_ton': Decimal(params.service_fee_nano) / Decimal('1000000000'),
            'insurance_ton': Decimal(params.insurance_nano) / Decimal('1000000000'),
            'purchase_deadline_ts': params.purchase_deadline_ts,
            'ship_deadline_ts': params.ship_deadline_ts,
            'confirm_deadline_ts': params.confirm_deadline_ts,
            'metadata_hash': params.metadata_hash_cell,
        }
        init_data_cell = build_deal_init_data_cell(init_params)
        print("✓ Init data cell created")
    except Exception as e:
        print(f"❌ Error creating init data cell: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Вычисляем адрес контракта
    try:
        contract_address = calculate_contract_address(code_cell, init_data_cell)
        print(f"✓ Contract address: {contract_address}")
    except Exception as e:
        print(f"❌ Error calculating contract address: {e}")
        return
    
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
    print("✓ State init created")
    
    # Для деплоя контракта через кошелек используем create_transfer_message
    # Это создает внутреннее сообщение от кошелька к контракту с state_init
    contract_addr = Address(contract_address)
    # Увеличиваем сумму для деплоя: нужно достаточно для активации контракта
    # Минимум ~0.1 TON для газа + комиссий, но лучше 0.2-0.3 TON для надежности
    deploy_amount_nano = to_nano(0.2, "ton")  # Увеличено до 0.2 TON для надежной активации
    
    print("✓ Using wallet.create_transfer_message for contract deployment")
    
    # Инициализируем TonCenter клиент один раз
    from core.ton_client import TonCenterClient
    ton_client = TonCenterClient()
    
    # Получаем статус кошелька и seqno
    wallet_address = wallet.address.to_string(True, True, True)
    
    # Сначала проверяем, есть ли seqno в переменной окружения (приоритет)
    manual_seqno = os.getenv("TON_WALLET_SEQNO")
    if manual_seqno:
        try:
            seqno = int(manual_seqno)
            print(f"✓ Using seqno from TON_WALLET_SEQNO environment variable: {seqno}")
        except ValueError:
            print(f"⚠️  Invalid TON_WALLET_SEQNO value: {manual_seqno}, will try to get from API")
            manual_seqno = None
    
    if not manual_seqno:
        try:
            # Сначала проверяем статус кошелька
            addr_info = ton_client.get_address_information(wallet_address)
            wallet_state = addr_info.get("state", "")
            wallet_balance = addr_info.get("balance", 0)
            print(f"✓ Wallet state: {wallet_state}, balance: {wallet_balance}")
            
            # Получаем seqno через API
            if wallet_state == "active":
                # Для активного кошелька пытаемся получить seqno
                seqno = None
                try:
                    seqno = ton_client.get_wallet_seqno(wallet_address)
                    if seqno > 0:
                        print(f"✓ Wallet seqno from API: {seqno}")
                    else:
                        # Если seqno=0, пробуем получить из последних транзакций
                        print(f"⚠️  API returned seqno=0, trying to get from transactions...")
                        try:
                            transactions = ton_client.get_transactions(wallet_address, limit=5)
                            if transactions and len(transactions) > 0:
                                # Ищем seqno в последних транзакциях
                                # Seqno обычно можно найти в структуре сообщения
                                # Для v3r2 кошелька seqno увеличивается с каждой транзакцией
                                # Пробуем найти максимальный seqno из транзакций
                                print(f"   Found {len(transactions)} recent transactions")
                                print(f"   ⚠️  Cannot extract seqno from transactions automatically")
                                print(f"   Please check TONScan for the latest seqno:")
                                print(f"   https://testnet.tonscan.org/address/{wallet_address}")
                                print(f"   Or try using seqno from the last successful transaction + 1")
                                seqno = None  # Не можем определить автоматически
                            else:
                                seqno = 0
                        except Exception as tx_error:
                            print(f"   Could not get transactions: {tx_error}")
                            seqno = 0
                except Exception as e:
                    print(f"⚠️  Could not get seqno for active wallet: {e}")
                    seqno = None
                
                if seqno is None or seqno == 0:
                    print(f"⚠️  Could not determine seqno automatically")
                    print(f"   For active wallet, you need the correct seqno!")
                    print(f"   Check TONScan: https://testnet.tonscan.org/address/{wallet_address}")
                    print(f"   Look for 'msg_seqno' in the last transaction")
                    print(f"   Using seqno=0 (will likely fail with exit code 33)")
                    seqno = 0
            else:
                # Для неинициализированного кошелька seqno=0
                print(f"✓ Wallet is {wallet_state}, using seqno=0")
                seqno = 0
        except Exception as e:
            print(f"⚠️  Could not get wallet info from API: {e}")
            print("   Using seqno=0 (for uninitialized wallet)")
            seqno = 0
    
    # Используем ручное создание сообщения с гарантированным state_init
    print("🔧 Using manual state_init deployment method (guaranteed state_init)...")
    use_manual = True
    try:
        from core.ton_deploy_tonutils import deploy_contract_with_manual_state_init
        
        contract_addr, tx_hash = deploy_contract_with_manual_state_init(
            code_cell=code_cell,
            init_data_cell=init_data_cell,
            amount_ton=Decimal('0.2'),
            wallet_mnemonic=mnemonic,
            seqno=seqno,
            network="testnet"
        )
        
        print(f"✓ Contract deployed successfully via manual state_init method")
        print(f"  Contract address: {contract_addr}")
        print(f"  Transaction hash: {tx_hash}")
        
        print("\n" + "=" * 70)
        print("✅ Contract deployment successful!")
        print("=" * 70)
        print(f"\nContract address: {contract_addr}")
        print(f"\n📋 Check contract on TONScan:")
        print(f"   https://testnet.tonscan.org/address/{contract_addr}")
        print("=" * 70)
        
        return  # Успешно завершаем
        
    except ImportError as e:
        print(f"⚠️  Manual state_init deployment method not available: {e}")
        print("   Falling back to tonsdk create_transfer_message...")
        use_manual = False
    except Exception as e:
        print(f"❌ Manual state_init deployment failed: {e}")
        import traceback
        traceback.print_exc()
        print("   Falling back to tonsdk create_transfer_message...")
        use_manual = False
    
    # Fallback: используем стандартный метод tonsdk (может не включать state_init)
    if not use_manual:
        print("\n🔧 Using tonsdk create_transfer_message (state_init may not be included)...")
        try:
            query = wallet.create_transfer_message(
                to_addr=contract_address,
                amount=deploy_amount_nano,
                seqno=seqno,
                state_init=state_init,
                payload=None,  # Без payload для деплоя нового контракта
                send_mode=3,  # send_mode=3: как в успешных транзакциях из TONScan
            )
            
            # Получаем сообщение из query
            if isinstance(query, dict):
                message = query.get("message")
            else:
                message = query
        
            # create_transfer_message создает внутреннее сообщение от кошелька к контракту
            # Это правильный способ для деплоя контракта через кошелек
            boc = message.to_boc(False)
            boc_b64 = bytes_to_b64str(boc)
            print(f"✓ Internal message created using wallet.create_transfer_message")
            print(f"  Message length: {len(boc)} bytes")
            print(f"  BOC base64 (first 100 chars): {boc_b64[:100]}...")
            
            # Проверяем, что state_init был включен в сообщение
            # Для этого проверяем размер BOC - с state_init он должен быть больше
            state_init_boc = state_init.to_boc(False)
            print(f"  State init size: {len(state_init_boc)} bytes")
            print(f"  Message BOC size: {len(boc)} bytes")
            if len(boc) < len(state_init_boc) + 500:  # Минимальный размер для сообщения с state_init
                print(f"  ⚠️  WARNING: Message size seems too small, state_init might not be included!")
                print(f"  ⚠️  create_transfer_message does not include state_init properly!")
                print(f"  💡 This is why we recommend using the manual deployment method above")
            else:
                print(f"  ✓ Message size looks correct, state_init should be included")
            
            print("\n" + "=" * 70)
            print("✅ Internal message created successfully!")
            if len(boc) < len(state_init_boc) + 500:
                print("⚠️  WARNING: State_init may not be included in the message!")
            print("=" * 70)
            print(f"\nContract address: {contract_address}")
            print(f"\nBOC (base64, first 200 chars): {boc_b64[:200]}...")
            print(f"BOC (base64, last 100 chars): ...{boc_b64[-100:]}")
            print(f"\nFull BOC length: {len(boc_b64)} characters")
            print("\n" + "=" * 70)
            
            # Пробуем отправить BOC через TonCenter API
            print("\n🚀 Attempting to send BOC via TonCenter API...")
            try:
                result = ton_client.send_boc(boc_b64)
                print("✅ BOC sent successfully!")
                print(f"   Result: {result}")
                print("\n" + "=" * 70)
                print(f"📋 Check contract on TONScan:")
                print(f"   https://testnet.tonscan.org/address/{contract_address}")
                print("=" * 70)
            except Exception as e:
                print(f"⚠️  Failed to send BOC: {e}")
                print("\n" + "=" * 70)
                print("BOC создан, но отправка не удалась.")
                print("Этот BOC можно отправить вручную через TonCenter API или другой инструмент.")
                print(f"\nContract address: {contract_address}")
                print(f"\nBOC length: {len(boc)} bytes")
                print("=" * 70)
        
        except Exception as e:
            print(f"❌ create_transfer_message failed: {e}")
            import traceback
            traceback.print_exc()
            return

if __name__ == "__main__":
    test_manual_deploy()

