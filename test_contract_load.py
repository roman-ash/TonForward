#!/usr/bin/env python
"""
Скрипт для проверки загрузки контракта Deal.
Можно запускать из контейнера Docker.
"""

import os
import sys
import django

# Настройка Django
sys.path.insert(0, 'buyer' if os.path.exists('buyer') else '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'buyer.settings')
django.setup()

def check_contract():
    """Проверяет загрузку контракта Deal."""
    
    print("=" * 60)
    print("Checking Deal Contract Setup")
    print("=" * 60)
    
    # Проверка 1: Переменная окружения
    print("\n1. Checking DEAL_CONTRACT_CODE_B64 environment variable...")
    deal_code = os.getenv("DEAL_CONTRACT_CODE_B64", "").strip()
    if deal_code:
        print(f"   ✓ Found (length: {len(deal_code)} characters)")
        print(f"   First 50 chars: {deal_code[:50]}...")
        print(f"   Last 50 chars: ...{deal_code[-50:]}")
    else:
        print("   ✗ NOT FOUND")
        print("   → Add DEAL_CONTRACT_CODE_B64 to .env file")
        print("   → Then restart container: docker-compose restart web")
        return False
    
    # Проверка 2: tonsdk
    print("\n2. Checking tonsdk library...")
    try:
        from tonsdk.boc import Cell
        from tonsdk.utils import b64str_to_bytes
        print(f"   ✓ tonsdk installed")
    except ImportError as e:
        print(f"   ✗ tonsdk NOT installed: {e}")
        print("   → Install with: pip install tonsdk")
        return False
    
    # Проверка 3: Загрузка контракта
    print("\n3. Loading contract code cell...")
    try:
        from core.ton_contracts import load_deal_code_cell
        code_cell = load_deal_code_cell()
        print(f"   ✓ Contract code cell loaded successfully!")
        print(f"   Cell type: {type(code_cell).__name__}")
        
        # Пробуем получить размер cell
        try:
            boc = code_cell.to_boc()
            print(f"   Cell BOC size: {len(boc)} bytes")
        except:
            pass
        
        return True
    except ImportError as e:
        print(f"   ✗ Import error: {e}")
        return False
    except ValueError as e:
        print(f"   ✗ Value error: {e}")
        return False
    except Exception as e:
        print(f"   ✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = check_contract()
    print("\n" + "=" * 60)
    if success:
        print("✓ All checks passed! Contract is ready to use.")
    else:
        print("✗ Some checks failed. See messages above.")
    print("=" * 60)
    sys.exit(0 if success else 1)

