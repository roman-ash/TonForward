# Руководство по компиляции Tact контракта Deal

## Проблема с синтаксисом

Если вы видите ошибку:
```
Duplicate immediate argument. Only first argument will be used
Unexpected immediate
```

Это означает, что синтаксис контракта не соответствует версии Tact compiler 1.6.

## Решение

### Вариант 1: Использовать упрощенную версию

Используйте файл `Deal_simple.tact` вместо `Deal.tact`. Он исправлен для Tact 1.6:

```bash
cd contracts
tact compile Deal_simple.tact
```

### Вариант 2: Исправить оригинальный контракт

Основные изменения для Tact 1.6:

1. **receive() функции** должны принимать типизированные сообщения:
   ```tact
   // Было (старый синтаксис):
   receive("mark_purchased") { ... }
   
   // Стало (новый синтаксис):
   message MarkPurchased {}
   receive(msg: MarkPurchased) { ... }
   ```

2. **context()** заменили на **ctx()**:
   ```tact
   // Было:
   context().sender
   
   // Стало:
   ctx().sender
   ```

3. **Slice** в init лучше заменить на **uint256**:
   ```tact
   // Для простоты используем uint256 вместо Slice
   metadataHash: Int as uint256
   ```

### Вариант 3: Использовать конфигурационный файл

Создайте `tact.config.json`:
```json
{
  "projects": [
    {
      "name": "Deal",
      "path": "./Deal_simple.tact",
      "output": "./output"
    }
  ]
}
```

Затем компилируйте:
```bash
tact --config tact.config.json
```

## Компиляция

После исправления синтаксиса:

```bash
cd contracts
tact compile Deal_simple.tact
```

Должно создать файлы:
- `Deal_simple.code.boc` - скомпилированный код
- `Deal_simple.code.fif` - FunC код

## Получение base64

После успешной компиляции:

```bash
# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("Deal_simple.code.boc")) | Out-File -Encoding ASCII Deal_simple.code.b64

# Или через Python
python -c "import base64; print(base64.b64encode(open('Deal_simple.code.boc', 'rb').read()).decode())"
```

Скопируйте содержимое в `.env`:
```
DEAL_CONTRACT_CODE_B64="<содержимое>"
```

## Важно!

После изменения контракта (использования uint256 вместо Slice), нужно также обновить `build_deal_init_data_cell()` в `buyer/core/ton_contracts.py`:

```python
# Заменить store_ref для metadataHash на store_uint
init_data = begin_cell()\
    ...
    .store_uint(metadata_hash_uint256, 256)\  # вместо store_ref
    .end_cell()
```

Где `metadata_hash_uint256` - это первые 32 bytes hash преобразованные в int.

