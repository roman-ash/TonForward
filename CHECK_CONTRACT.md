# Проверка загрузки контракта Deal

## Проблемы и решения

### Проблема 1: В IDE `tonsdk` не установлен

**Ошибка:**
```
ImportError: tonsdk is required for contract operations
```

**Решение:**
Это нормально для локальной разработки. `tonsdk` нужен только в Docker контейнере.

Если хотите тестировать локально, установите:
```bash
pip install tonsdk
```

Но это не обязательно - контракт будет работать в контейнере.

### Проблема 2: В контейнере переменная `DEAL_CONTRACT_CODE_B64` не видна

**Ошибка:**
```
ValueError: DEAL_CONTRACT_CODE_B64 environment variable is required
```

**Решение:**

1. **Проверьте, что переменная добавлена в `.env` файл:**
   ```bash
   # В корне проекта (.env)
   DEAL_CONTRACT_CODE_B64="te6ccgECGwEAB24AART/..."
   ```

2. **Перезапустите контейнер после добавления переменной:**
   ```bash
   docker-compose restart web
   docker-compose restart celery
   ```
   
   Или полностью пересоберите:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

3. **Проверьте, что переменная видна в контейнере:**
   ```bash
   docker-compose exec web python manage.py shell
   >>> import os
   >>> print(os.getenv('DEAL_CONTRACT_CODE_B64', 'NOT FOUND')[:50])
   ```

## Проверка загрузки контракта

### Из контейнера (рекомендуется):

```bash
docker-compose exec web python test_contract_load.py
```

Или через Django shell:

```bash
docker-compose exec web python manage.py shell
```

```python
>>> from core.ton_contracts import load_deal_code_cell
>>> code_cell = load_deal_code_cell()
>>> print("✓ Contract loaded!")
```

### Из IDE (если установлен tonsdk):

```python
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'buyer.settings')
django.setup()

# Загрузите переменную из .env вручную
from dotenv import load_dotenv
load_dotenv()

from core.ton_contracts import load_deal_code_cell
code_cell = load_deal_code_cell()
print("✓ Contract loaded!")
```

## Важно!

- **`.env` файл должен быть в корне проекта** (рядом с `docker-compose.yml`)
- **После изменения `.env` нужно перезапустить контейнеры**
- **Переменная читается только в Docker контейнере**, не в локальной IDE (если не использовать `python-dotenv`)

