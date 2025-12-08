# Руководство по Git для проекта

## Что коммитится в Git

### ✅ Коммитим:
- Исходный код Python (`buyer/`, `core/`, `user/`)
- Исходники контрактов (`contracts/*.tact`)
- Конфигурационные файлы (`docker-compose.yml`, `Dockerfile`, `requirements.txt`)
- Документация (`*.md` файлы)
- Скрипты компиляции (`contracts/compile.sh`, `contracts/compile_contract.cmd`)

### ❌ НЕ коммитим (через .gitignore):

1. **Секреты:**
   - `.env` - все переменные окружения (ключа API, mnemonic, пароли)

2. **Скомпилированные файлы контрактов:**
   - `contracts/output/` - все скомпилированные файлы
   - `contracts/*.b64` - base64 файлы с кодом контракта
   - `contracts/*.boc` - бинарные BOC файлы

3. **Python:**
   - `venv/` - виртуальное окружение
   - `__pycache__/` - кеш Python
   - `*.pyc`, `*.pyo` - байткод

4. **Django:**
   - `*.log` - логи
   - `db.sqlite3` - база данных
   - `/staticfiles`, `/media` - статика и медиа

5. **Celery:**
   - `celerybeat-schedule*` - файлы расписания

6. **IDE:**
   - `.vscode/`, `.idea/` - настройки IDE

7. **Docker:**
   - `pgdata/` - данные PostgreSQL

## Важно!

### ⚠️ НЕ КОММИТЬТЕ:
- **`.env`** - содержит секретные ключи и пароли
- **`DEAL_CONTRACT_CODE_B64`** в `.env` - это не секрет, но лучше не коммитить
- **Скомпилированные контракты** - их можно пересобрать

### ✅ МОЖНО КОММИТЬ:
- Исходники контрактов (`contracts/Deal_simple.tact`)
- Документацию по контрактам
- Конфигурацию проекта

## Перед первым коммитом

1. Проверьте `.gitignore`:
   ```bash
   cat .gitignore
   ```

2. Проверьте, что `.env` игнорируется:
   ```bash
   git status
   # .env не должен показываться
   ```

3. Проверьте, что скомпилированные файлы игнорируются:
   ```bash
   git status contracts/
   # contracts/output/ и contracts/*.b64 не должны показываться
   ```

## Пример безопасного .env для документации

Создайте `.env.example` (это можно коммитить):

```bash
# Database
DB_HOST=db
DB_NAME=buyer
DB_USER=postgres_user
DB_PASS=your_password_here

# TON Blockchain
TON_PROVIDER_URL=https://toncenter.com/api/v2
TONCENTER_API_KEY=your_api_key_here
TON_SERVICE_WALLET_PRIVATE_KEY=your_private_key_here
TON_SERVICE_WALLET=your_service_wallet_address
TON_ARBITER_WALLET=your_arbiter_wallet_address

# TON Wallet
TON_MNEMONIC="word1 word2 ... word24"

# Contract Code (after compilation)
DEAL_CONTRACT_CODE_B64="your_base64_code_here"

# Payment Providers
YOOKASSA_SECRET_KEY=your_yookassa_key
TINKOFF_SECRET_KEY=your_tinkoff_key

# Django
SECRET_KEY=your_secret_key_here
DEBUG=True
```

## Рекомендации

1. **Никогда не коммитьте `.env`** с реальными ключами
2. **Используйте `.env.example`** как шаблон для других разработчиков
3. **Проверяйте `git status`** перед каждым коммитом
4. **Используйте `git diff`** для проверки изменений

