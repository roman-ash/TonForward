#!/usr/bin/env python
"""
Скрипт для создания TON кошелька.
⚠️ ВНИМАНИЕ: Запускайте только локально, не в production окружении!

Использование:
    python create_wallet.py

Требования:
    pip install tonsdk mnemonic
"""

import sys

try:
    from tonsdk.contract.wallet import Wallets, WalletVersionEnum
    from mnemonic import Mnemonic
except ImportError:
    print("❌ Ошибка: Установите зависимости:")
    print("   pip install tonsdk mnemonic")
    sys.exit(1)


def create_wallet(wallet_name: str = "Service Wallet"):
    """
    Создает новый TON кошелек и выводит информацию.
    
    Args:
        wallet_name: Имя кошелька (для вывода)
    """
    print("=" * 70)
    print(f"CREATING {wallet_name.upper()}")
    print("=" * 70)
    
    print("\n⚠️  ВАЖНО: Сохраните эту информацию в безопасном месте!")
    print("⚠️  НИКОГДА не коммитьте mnemonic в Git!")
    print("=" * 70)
    
    # Используем надежный способ: генерируем mnemonic через tonsdk.crypto.mnemonic_new
    # и создаем кошелек через from_mnemonics
    try:
        from tonsdk.crypto import mnemonic_new
        
        # Генерируем mnemonic через tonsdk (правильный формат, гарантированно валидный)
        mnemonic_list = mnemonic_new()
        mnemonic_words = " ".join(mnemonic_list)
        
        # Создаем кошелек из сгенерированного mnemonic
        wallet_result = Wallets.from_mnemonics(
            mnemonics=mnemonic_list,
            wallet_version=WalletVersionEnum.v4r2,
            workchain=0
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
                # Возможно первый элемент - это список с wallet внутри
                first_item = wallet_result[0]
                if isinstance(first_item, (list, tuple)) and len(first_item) > 0:
                    wallet = first_item[0]
                else:
                    wallet = first_item
        else:
            wallet = wallet_result
        
        # Проверяем, что wallet создан правильно
        if isinstance(wallet, (tuple, list)):
            # Если все еще кортеж/список, ищем элемент с address
            for item in wallet:
                if hasattr(item, 'address'):
                    wallet = item
                    break
            else:
                wallet = wallet[0] if len(wallet) > 0 else None
        
        if wallet is None or not hasattr(wallet, 'address'):
            # Выводим детальную информацию для отладки
            debug_info = []
            if isinstance(wallet_result, tuple):
                for i, item in enumerate(wallet_result):
                    debug_info.append(f"  [{i}]: type={type(item).__name__}, has_address={hasattr(item, 'address')}")
                    if isinstance(item, (list, tuple)) and len(item) > 0:
                        debug_info.append(f"    -> First element: type={type(item[0]).__name__}, has_address={hasattr(item[0], 'address')}")
            raise ValueError(
                f"Could not find wallet object with 'address' attribute.\n"
                f"Result type: {type(wallet_result)}, "
                f"Result length: {len(wallet_result) if isinstance(wallet_result, tuple) else 'N/A'}\n"
                f"Wallet type: {type(wallet) if wallet else 'None'}\n"
                f"Tuple contents:\n" + "\n".join(debug_info)
            )
            
    except ImportError:
        # Fallback: если mnemonic_new недоступен, используем библиотеку mnemonic
        # но это менее надежно, так как формат может не совпадать
        try:
            mnemonic_generator = Mnemonic("english")
            mnemonic_words = mnemonic_generator.generate(256)  # 256 бит = 24 слова
            mnemonic_list = mnemonic_words.split()
            
            # Валидируем mnemonic
            if not mnemonic_generator.check(mnemonic_words):
                raise ValueError("Generated mnemonic is invalid")
            
            # Проверяем количество слов
            if len(mnemonic_list) != 24:
                raise ValueError(f"Invalid mnemonic length: expected 24 words, got {len(mnemonic_list)}")
            
            # Создаем кошелек
            wallet_result = Wallets.from_mnemonics(
                mnemonics=mnemonic_list,
                wallet_version=WalletVersionEnum.v4r2,
                workchain=0
            )
            
            # Обрабатываем результат - может быть кортеж или объект
            if isinstance(wallet_result, tuple):
                # Ищем элемент с атрибутом 'address'
                wallet = None
                for item in wallet_result:
                    if hasattr(item, 'address'):
                        wallet = item
                        break
                
                if wallet is None and len(wallet_result) > 0:
                    first_item = wallet_result[0]
                    if isinstance(first_item, (list, tuple)) and len(first_item) > 0:
                        wallet = first_item[0]
                    else:
                        wallet = first_item
            else:
                wallet = wallet_result
            
            if wallet is None or not hasattr(wallet, 'address'):
                raise ValueError(
                    f"Could not extract valid wallet from result: {type(wallet_result)}, "
                    f"length: {len(wallet_result) if isinstance(wallet_result, tuple) else 'N/A'}"
                )
        except Exception as fallback_error:
            raise RuntimeError(
                f"Could not create wallet.\n"
                f"Error: {fallback_error}\n"
                f"Make sure tonsdk is properly installed: pip install tonsdk\n"
                f"Also install mnemonic library: pip install mnemonic"
            )
    
    # Получаем адрес в разных форматах
    address = wallet.address.to_string(True, True, True)  # user-friendly format
    address_raw = wallet.address.to_string(False, False, False)  # raw format
    
    # Получаем публичный ключ (разные версии wallet могут иметь разные атрибуты)
    try:
        if hasattr(wallet, 'public_key'):
            public_key = wallet.public_key
        elif hasattr(wallet, 'publickey'):
            public_key = wallet.publickey
        elif hasattr(wallet, 'publicKey'):
            public_key = wallet.publicKey
        elif hasattr(wallet, 'keys'):
            # Возможно ключи хранятся в словаре keys
            public_key = wallet.keys.get('public') if isinstance(wallet.keys, dict) else wallet.keys[1] if isinstance(wallet.keys, (list, tuple)) else None
        else:
            # Пробуем получить через приватный ключ
            if hasattr(wallet, 'private_key'):
                from tonsdk.crypto import private_to_public_key
                public_key = private_to_public_key(wallet.private_key)
            else:
                public_key = None
                print("⚠️  Warning: Could not extract public key from wallet")
    except Exception as e:
        print(f"⚠️  Warning: Could not extract public key: {e}")
        public_key = None
    
    print(f"\n📝 MNEMONIC PHRASE (24 words):")
    print(f"\n{mnemonic_words}\n")
    print("-" * 70)
    
    print(f"\n📍 WALLET ADDRESS (user-friendly):")
    print(f"{address}\n")
    print("-" * 70)
    
    print(f"\n📍 WALLET ADDRESS (raw):")
    print(f"{address_raw}\n")
    print("-" * 70)
    
    if public_key is not None:
        # Преобразуем публичный ключ в hex строку
        if hasattr(public_key, 'hex'):
            public_key_hex = public_key.hex()
        elif isinstance(public_key, bytes):
            public_key_hex = public_key.hex()
        elif isinstance(public_key, (list, tuple)):
            public_key_hex = bytes(public_key).hex()
        else:
            public_key_hex = str(public_key)
        
        print(f"\n🔑 PUBLIC KEY:")
        print(f"{public_key_hex}\n")
    print("=" * 70)
    
    print("\n✅ Добавьте в .env файл:")
    print("=" * 70)
    print(f'\nTON_MNEMONIC="{mnemonic_words}"')
    print(f'TON_SERVICE_WALLET="{address}"')
    print("\n" + "=" * 70)
    print("⚠️  НИКОГДА не коммитьте .env файл в Git!")
    print("⚠️  Храните mnemonic в безопасном месте (password manager)!")
    print("=" * 70)
    
    # Форматируем public_key для возврата
    if public_key is not None:
        if hasattr(public_key, 'hex'):
            public_key_str = public_key.hex()
        elif isinstance(public_key, bytes):
            public_key_str = public_key.hex()
        elif isinstance(public_key, (list, tuple)):
            public_key_str = bytes(public_key).hex()
        else:
            public_key_str = str(public_key)
    else:
        public_key_str = None
    
    return {
        'mnemonic': mnemonic_words,
        'address': address,
        'address_raw': address_raw,
        'public_key': public_key_str
    }


if __name__ == "__main__":
    print("\n🚀 TON Wallet Creator")
    print("\nЭтот скрипт создаст новый TON кошелек с mnemonic фразой.")
    print("Используйте его для получения переменных окружения для проекта.\n")
    
    # Создаем сервисный кошелек
    service_wallet = create_wallet("Service Wallet")
    
    print("\n\n")
    input("Нажмите Enter для создания кошелька арбитра (или Ctrl+C для отмены)...")
    
    # Создаем кошелек арбитра
    arbiter_wallet = create_wallet("Arbiter Wallet")
    
    print("\n\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("\nДобавьте в .env файл:")
    print("-" * 70)
    print(f'\nTON_MNEMONIC="{service_wallet["mnemonic"]}"')
    print(f'TON_SERVICE_WALLET="{service_wallet["address"]}"')
    print(f'TON_ARBITER_WALLET="{arbiter_wallet["address"]}"')
    print("\n" + "=" * 70)


