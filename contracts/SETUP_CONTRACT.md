# Настройка скомпилированного контракта Deal

## ✅ Компиляция завершена успешно!

Файлы в `output/`:
- ✅ `Deal_Deal.code.boc` - скомпилированный код контракта (1914 bytes)
- ✅ `Deal_Deal.code.b64` - код в base64 формате (2552 chars)

## 📋 Добавление в проект

### Шаг 1: Получить base64 код

Файл уже создан: `contracts/Deal_Deal.code.b64`

### Шаг 2: Добавить в .env

Откройте `.env` файл в корне проекта и добавьте:

```bash
DEAL_CONTRACT_CODE_B64="<содержимое из contracts/Deal_Deal.code.b64>"
```

**Или скопируйте одной командой (Windows PowerShell):**
```powershell
$b64 = Get-Content contracts/Deal_Deal.code.b64 -Raw
Add-Content -Path .env -Value "DEAL_CONTRACT_CODE_B64=`"$b64`""
```

### Шаг 3: Проверка загрузки

После добавления в `.env` проверьте:

```python
python manage.py shell
```

```python
>>> from core.ton_contracts import load_deal_code_cell
>>> code_cell = load_deal_code_cell()
>>> print(f"✓ Contract code loaded! Cell type: {type(code_cell)}")
```

## 📊 Информация о контракте

- **Размер BOC**: 1914 bytes
- **Размер base64**: 2552 символов
- **Методы**: 
  - `mark_purchased`, `mark_shipped`, `confirm_delivery`
  - `cancel_before_purchase`, `cancel_before_ship`
  - `auto_complete_for_buyer`
  - `open_dispute`
  - `resolve_dispute_refund_customer`, `resolve_dispute_pay_buyer`, `resolve_dispute_split`
- **GET методы**: `get_status`, `get_data`

## 🔍 Структура init data

Параметры контракта (в порядке):
1. `customer: Address`
2. `buyer: Address`
3. `serviceWallet: Address`
4. `arbiter: Address`
5. `itemPriceNano: Coins`
6. `buyerFeeNano: Coins`
7. `serviceFeeNano: Coins`
8. `insuranceNano: Coins`
9. `purchaseDeadline: UInt64`
10. `shipDeadline: UInt64`
11. `confirmDeadline: UInt64`
12. `metadataHash: UInt256`

Это соответствует функции `build_deal_init_data_cell()` в `buyer/core/ton_contracts.py`.

## ✅ Готово!

После добавления `DEAL_CONTRACT_CODE_B64` в `.env`, контракт будет автоматически загружаться при деплое сделок через Celery задачу `deploy_onchain_deal`.

