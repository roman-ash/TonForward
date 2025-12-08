# Интеграция с TON Blockchain

Этот документ описывает интеграцию проекта с TON blockchain для деплоя и работы со смарт-контрактами Deal.

## Структура модулей

### `ton_client.py`
HTTP клиент для работы с TonCenter API v2. Тонкая обёртка для отправки запросов к TON blockchain.

**Основные методы:**
- `send_boc(boc_base64)` - отправка BOC транзакции
- `get_address_information(address)` - получение информации об адресе
- `run_get_method(address, method, stack)` - вызов GET метода контракта
- `get_wallet_seqno(address)` - получение seqno кошелька

### `ton_wallet.py`
Сервис для работы с TON кошельком. Управляет сервисным кошельком, подписывает и отправляет транзакции.

**Основные методы:**
- `deploy_contract(code_cell, init_data_cell, amount_ton)` - деплой контракта
- `send_transfer(to_address, amount_ton, comment)` - отправка TON

### `ton_contracts.py`
Модуль для работы с контрактами Deal.

**Основные функции:**
- `load_deal_code_cell()` - загрузка кода контракта Deal
- `build_deal_init_data_cell(params)` - сборка init data для контракта
- `calculate_contract_address(code_cell, init_data_cell)` - вычисление адреса контракта

### `ton_utils.py`
Утилиты для работы с TON blockchain. Содержит высокоуровневые функции для деплоя и вызова методов контрактов.

**Основные функции:**
- `deploy_onchain_deal(params)` - деплой контракта Deal
- `call_contract_method(contract_address, method_name, params)` - вызов метода контракта
- `get_contract_state(contract_address)` - получение состояния контракта
- `sync_deal_status_from_chain(onchain_deal)` - синхронизация статусов

## Настройка

### 1. Установка зависимостей

```bash
pip install httpx>=0.24.0 tonsdk>=2.0.0
```

### 2. Переменные окружения

Добавьте в `.env`:

```bash
# TonCenter API
TONCENTER_API_KEY=your_api_key_here
TONCENTER_URL=https://toncenter.com/api/v2

# TON кошелек
TON_MNEMONIC="word1 word2 ... word24"  # 24 слова mnemonic фразы сервисного кошелька

# Адреса
TON_SERVICE_WALLET=EQ...  # Адрес сервисного кошелька
TON_ARBITER_WALLET=EQ...  # Адрес арбитра

# Код контракта Deal (после компиляции Tact)
DEAL_CONTRACT_CODE_B64="te6cckEBAQEA..."  # Base64 BOC скомпилированного контракта
```

### 3. Компиляция Tact контракта Deal

1. Скомпилируйте ваш Tact контракт Deal
2. Получите BOC код контракта (обычно в файле `deal.code.boc`)
3. Конвертируйте в base64 и добавьте в `DEAL_CONTRACT_CODE_B64`

Пример:
```bash
base64 -i deal.code.boc > deal.code.b64
```

Затем скопируйте содержимое в переменную окружения.

## Использование

### Деплой контракта

Контракт автоматически деплоится через Celery задачу `deploy_onchain_deal` после успешного платежа:

```python
from core.tasks import deploy_onchain_deal

# Задача запускается автоматически через webhook после успешного платежа
deploy_onchain_deal.delay(deal_id)
```

### Вызов методов контракта

```python
from core.ton_utils import call_contract_method

result = call_contract_method(
    contract_address="EQ...",
    method_name="mark_purchased",
    params={"stack": []}
)
```

### Получение состояния контракта

```python
from core.ton_utils import get_contract_state

state = get_contract_state("EQ...")
print(f"Balance: {state['balance']}, Status: {state['status']}")
```

## Адаптация под ваш контракт

### Изменение структуры init data

В `ton_contracts.py` функция `build_deal_init_data_cell` должна соответствовать `init()` функции вашего Tact контракта.

Пример для контракта с такой сигнатурой:
```tact
init(
    customer: Address,
    buyer: Address,
    serviceWallet: Address,
    arbiter: Address,
    itemPriceNano: Int,
    buyerFeeNano: Int,
    serviceFeeNano: Int,
    insuranceNano: Int,
    purchaseDeadline: Int,
    shipDeadline: Int,
    confirmDeadline: Int,
    metadataHash: Slice
)
```

Если структура отличается, измените `build_deal_init_data_cell` соответственно.

## Fallback режим (Mock)

Если переменные окружения не установлены или библиотеки не доступны, система автоматически переходит в mock режим:
- Генерируются фиктивные адреса контрактов
- Методы возвращают mock результаты
- Логируется предупреждение

Это позволяет разрабатывать и тестировать проект без реального подключения к TON blockchain.

## Отладка

Все операции логируются через стандартный logger Django:
```python
import logging
logger = logging.getLogger('core.ton_utils')
logger.setLevel(logging.DEBUG)
```

В логах вы увидите:
- Информацию о деплое контрактов
- Результаты вызовов методов
- Ошибки и предупреждения

## Дальнейшее развитие

1. **Собственная нода**: Можно заменить TonCenter на собственную TON ноду, изменив только `TonCenterClient`
2. **Кэширование**: Добавить кэширование состояния контрактов
3. **Retry логика**: Добавить автоматические повторы для failed транзакций
4. **Мониторинг**: Добавить мониторинг деплоев и транзакций

