# TON Smart Contracts

Этот каталог содержит Tact контракты для проекта.

## Контракт Deal

`Deal.tact` - смарт-контракт для escrow сделок между заказчиком и байером.

### Структура init() параметров

```tact
init(
    customer: Address,           // Адрес заказчика
    buyer: Address,              // Адрес байера
    serviceWallet: Address,      // Адрес сервисного кошелька
    arbiter: Address,            // Адрес арбитра
    itemPriceNano: Int,          // Цена товара в nanoTON
    buyerFeeNano: Int,           // Комиссия байера в nanoTON
    serviceFeeNano: Int,         // Комиссия сервиса в nanoTON
    insuranceNano: Int,          // Страховка в nanoTON
    purchaseDeadline: Int,       // Unix timestamp дедлайна покупки
    shipDeadline: Int,           // Unix timestamp дедлайна отправки
    confirmDeadline: Int,        // Unix timestamp дедлайна подтверждения
    metadataHash: Slice          // Hash метаданных (32 bytes)
)
```

### Статусы контракта

- 0 = NEW
- 1 = FUNDED (после деплоя)
- 2 = PURCHASED
- 3 = SHIPPED
- 4 = COMPLETED
- 5 = CANCELLED_REFUND_CUSTOMER
- 6 = CANCELLED_PAY_BUYER
- 7 = DISPUTE

### Доступные методы

- `mark_purchased()` - байер отмечает товар как купленный
- `mark_shipped()` - байер отмечает товар как отправленный
- `confirm_delivery()` - заказчик подтверждает получение
- `cancel_before_purchase()` - отмена до покупки
- `cancel_before_ship()` - отмена до отправки
- `auto_complete_for_buyer()` - автоматическое завершение для байера
- `open_dispute()` - открытие спора
- `resolve_dispute_refund_customer()` - разрешение спора в пользу заказчика
- `resolve_dispute_pay_buyer()` - разрешение спора в пользу байера
- `resolve_dispute_split()` - разделение средств пополам

## Компиляция

### Установка Tact compiler

**Важно:** Устанавливайте локально (в IDE), не в Docker контейнере!

#### Способ 1: Через npm (рекомендуется)
```bash
npm install -g @tact-lang/compiler
```

#### Способ 2: Через binary
Скачайте с https://github.com/tact-lang/tact/releases

#### Способ 3: Через npx (без установки)
```bash
npx @tact-lang/compiler compile Deal.tact
```

### Компиляция контракта

```bash
cd contracts
bash compile.sh
```

Или вручную:

```bash
tact compile Deal.tact
```

### Получение BOC кода для деплоя

После компиляции конвертируйте BOC в base64:

```bash
base64 -i Deal.code.boc > Deal.code.b64
```

Затем скопируйте содержимое `Deal.code.b64` в переменную окружения:

```bash
DEAL_CONTRACT_CODE_B64="<содержимое файла>"
```

## Тестирование

Перед деплоем на mainnet протестируйте контракт на testnet:

1. Деплой на testnet
2. Проверка всех методов
3. Проверка распределения средств

## Безопасность

⚠️ **ВАЖНО**: Перед использованием на mainnet:

1. Проведите аудит кода контракта
2. Протестируйте все сценарии на testnet
3. Убедитесь в правильности распределения средств
4. Проверьте обработку edge cases (дедлайны, споры и т.д.)

