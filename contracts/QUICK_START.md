# Быстрый старт - Компиляция контракта Deal

## Проблема

Ошибка при компиляции:
```
Duplicate immediate argument. Only first argument will be used
Unexpected immediate
```

## Решение

### Шаг 1: Используйте упрощенную версию контракта

Файл `Deal_simple.tact` исправлен для Tact 1.6.13.

### Шаг 2: Компиляция

В терминале (CMD, не PowerShell):

```cmd
cd contracts
tact compile Deal_simple.tact
```

### Шаг 3: Получение base64

**Windows PowerShell:**
```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("Deal_simple.code.boc")) | Out-File -Encoding ASCII Deal_simple.code.b64
Get-Content Deal_simple.code.b64
```

**Или через Python:**
```python
import base64

with open('Deal_simple.code.boc', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('ascii')
    print(b64)
    
    with open('Deal_simple.code.b64', 'w') as out:
        out.write(b64)
```

### Шаг 4: Добавление в проект

Скопируйте содержимое `Deal_simple.code.b64` в `.env`:

```bash
DEAL_CONTRACT_CODE_B64="<содержимое файла>"
```

## Что изменилось в Deal_simple.tact

1. ✅ Типизированные сообщения вместо строк в receive()
2. ✅ `ctx()` вместо `context()`
3. ✅ `uint256` вместо `Slice` для metadataHash

## Проверка

После добавления в `.env` проверьте загрузку:

```python
python manage.py shell
>>> from core.ton_contracts import load_deal_code_cell
>>> code_cell = load_deal_code_cell()
>>> print("✓ Contract loaded!")
```

