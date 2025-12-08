# Компиляция контракта - Решение проблемы

## Статус

✅ **Синтаксис проверен успешно!** (`tact --check` прошел)

❌ Проблема с `tact compile` - ошибка "Duplicate immediate argument"

## Решение

### Вариант 1: Использовать конфигурационный файл (рекомендуется)

```cmd
cd contracts
tact --config tact.config.json
```

Конфиг файл обновлен и указывает на `Deal_simple.tact`.

### Вариант 2: Указать выходную директорию

```cmd
cd contracts
tact compile -o output Deal_simple.tact
```

### Вариант 3: Использовать скрипт (для CMD)

Запустите в **CMD** (не PowerShell):
```cmd
cd contracts
compile_contract.cmd
```

### Вариант 4: Попробовать с флагом --quiet

```cmd
cd contracts
tact --quiet compile Deal_simple.tact
```

## После успешной компиляции

После компиляции вы найдете файлы в директории `output/`:

- `Deal_simple.code.boc` - скомпилированный код контракта
- `Deal_simple.code.fif` - FunC код (опционально)

### Получение base64

**Windows PowerShell:**
```powershell
cd output
[Convert]::ToBase64String([IO.File]::ReadAllBytes("Deal_simple.code.boc")) | Out-File -Encoding ASCII ../Deal_simple.code.b64
Get-Content ../Deal_simple.code.b64
```

**Или через Python:**
```python
import base64

with open('output/Deal_simple.code.boc', 'rb') as f:
    b64 = base64.b64encode(f.read()).decode('ascii')
    
    with open('Deal_simple.code.b64', 'w') as out:
        out.write(b64)
    
    print(b64[:100] + "...")
```

### Добавление в .env

Скопируйте содержимое `Deal_simple.code.b64` в `.env`:
```
DEAL_CONTRACT_CODE_B64="<содержимое файла>"
```

