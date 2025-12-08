# Инструкция по компиляции Tact контракта Deal

## Шаг 1: Установка Tact compiler

### ⚠️ Где устанавливать?

**Устанавливайте в IDE/локально, НЕ в контейнере Docker!**

Компиляция контракта - это разовая операция, которую нужно делать локально или в CI/CD, но не в продакшн контейнере.

### Вариант 1: Через npm (рекомендуется)

```bash
npm install -g @tact-lang/compiler
```

После установки проверьте:
```bash
tact --version
```

### Вариант 2: Через binary release

1. Перейдите на https://github.com/tact-lang/tact/releases
2. Скачайте последнюю версию для вашей ОС:
   - Windows: `tact-windows-x64.exe`
   - Linux: `tact-linux-x64`
   - macOS: `tact-macos-x64`
3. Переименуйте файл в `tact` (на Linux/macOS) или `tact.exe` (на Windows)
4. Добавьте в PATH или используйте с полным путем

### Вариант 3: Через npx (без глобальной установки)

```bash
npx @tact-lang/compiler compile Deal.tact
```

## Шаг 2: Компиляция контракта

```bash
cd contracts
tact compile Deal.tact
```

После успешной компиляции вы получите файлы:
- `Deal.code.boc` - скомпилированный код контракта
- `Deal.code.fif` - FIF формат (опционально)

## Шаг 3: Конвертация в base64

### Linux/Mac:

```bash
base64 -i Deal.code.boc > Deal.code.b64
cat Deal.code.b64
```

### Windows (PowerShell):

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("Deal.code.boc")) | Out-File -Encoding ASCII Deal.code.b64
Get-Content Deal.code.b64
```

### Python:

```python
import base64

with open('Deal.code.boc', 'rb') as f:
    boc_data = f.read()
    b64_data = base64.b64encode(boc_data).decode('ascii')
    
with open('Deal.code.b64', 'w') as f:
    f.write(b64_data)

print(b64_data)
```

## Шаг 4: Добавление в проект

Скопируйте содержимое `Deal.code.b64` и добавьте в `.env`:

```bash
DEAL_CONTRACT_CODE_B64="<содержимое из Deal.code.b64>"
```

Или установите как переменную окружения в системе:

```bash
export DEAL_CONTRACT_CODE_B64="<содержимое>"
```

## Проверка

После установки переменной окружения проверьте, что контракт загружается:

```python
from core.ton_contracts import load_deal_code_cell

try:
    code_cell = load_deal_code_cell()
    print("✓ Contract code loaded successfully")
except Exception as e:
    print(f"✗ Error: {e}")
```

## Пример полного процесса

```bash
# 1. Установка Tact
npm install -g @tact-lang/tact

# 2. Компиляция
cd contracts
tact compile Deal.tact

# 3. Конвертация в base64 (Linux/Mac)
base64 -i Deal.code.boc > Deal.code.b64

# 4. Копирование в .env
echo 'DEAL_CONTRACT_CODE_B64="'$(cat Deal.code.b64)'"' >> ../.env

# 5. Или установка переменной окружения
export DEAL_CONTRACT_CODE_B64="$(cat Deal.code.b64)"
```

## Устранение проблем

### Ошибка: "tact: command not found"

Убедитесь, что Tact compiler установлен и доступен в PATH:

```bash
which tact
tact --version
```

### Ошибка при компиляции

Проверьте синтаксис контракта:

```bash
tact compile Deal.tact --verbose
```

### Неверный формат BOC

Убедитесь, что файл `Deal.code.boc` создан и не пустой:

```bash
ls -lh Deal.code.boc
file Deal.code.boc
```

