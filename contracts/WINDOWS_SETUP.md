# Установка Tact на Windows - Решение проблем

## Предупреждения при установке

### 1. EBADENGINE (Node.js версия)

**Это НЕ критично!** 

Если вы видите:
```
npm WARN EBADENGINE required: { node: '>=22.0.0' }, current: { node: 'v20.11.1' }
```

Это просто предупреждение. Tact обычно работает и на Node.js 20. Если `tact --version` работает - все ок!

### 2. Deprecated inflight

**Это НЕ критично!** Это зависимость других пакетов, можно игнорировать.

## Проблема с PowerShell Execution Policy

Если вы видите ошибку:
```
Невозможно загрузить файл ... так как выполнение сценариев отключено в этой системе
```

### Решение 1: Использовать CMD вместо PowerShell

1. Откройте **Командную строку (CMD)**, а не PowerShell
2. Запустите там:
   ```cmd
   tact --version
   ```

### Решение 2: Изменить Execution Policy в PowerShell

Откройте PowerShell **от имени администратора** и выполните:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Затем перезапустите PowerShell.

### Решение 3: Использовать npx (без глобальной установки)

Вместо `tact` используйте:
```bash
npx @tact-lang/compiler compile Deal.tact
```

### Решение 4: Запустить напрямую через npm

```bash
npm exec -- tact --version
```

## Проверка установки

После установки проверьте в **CMD** (не PowerShell):

```cmd
tact --version
```

Должно показать версию, например: `1.6.13`

## Компиляция контракта

Когда Tact работает, скомпилируйте контракт:

```cmd
cd contracts
tact compile Deal.tact
```

Если используется PowerShell с измененной Execution Policy:
```powershell
cd contracts
tact compile Deal.tact
```

## Рекомендация

**Используйте CMD для работы с Tact на Windows**, чтобы избежать проблем с Execution Policy.

