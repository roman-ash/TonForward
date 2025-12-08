# Установка Tact Compiler

## 🔧 Где устанавливать?

**В терминале IDE/локальной системе, НЕ в Docker контейнере!**

Компиляция контрактов выполняется один раз при разработке, поэтому лучше делать это локально.

## Способ 1: Через npm (Windows/Linux/macOS)

```bash
npm install -g @tact-lang/compiler
```

**Важно:** Правильный пакет называется `@tact-lang/compiler`, а не `@tact-lang/tact`!

Проверка установки:
```bash
tact --version
```

## Способ 2: Через binary (если npm не работает)

### Windows:

1. Перейдите на https://github.com/tact-lang/tact/releases
2. Скачайте `tact-windows-x64.exe`
3. Переименуйте в `tact.exe`
4. Поместите в папку, которая в PATH, или используйте с полным путем

### Linux:

```bash
# Скачать binary
wget https://github.com/tact-lang/tact/releases/latest/download/tact-linux-x64

# Сделать исполняемым
chmod +x tact-linux-x64

# Переместить в /usr/local/bin
sudo mv tact-linux-x64 /usr/local/bin/tact

# Проверить
tact --version
```

### macOS:

```bash
# Скачать binary
wget https://github.com/tact-lang/tact/releases/latest/download/tact-macos-x64

# Сделать исполняемым
chmod +x tact-macos-x64

# Переместить в /usr/local/bin
sudo mv tact-macos-x64 /usr/local/bin/tact

# Проверить
tact --version
```

## Способ 3: Через npx (без установки)

Если не хотите устанавливать глобально:

```bash
npx @tact-lang/compiler compile Deal.tact
```

Или создайте npm script в `package.json`:

```json
{
  "scripts": {
    "compile-tact": "npx @tact-lang/compiler compile contracts/Deal.tact"
  }
}
```

## Устранение проблем

### Ошибка: "npm ERR! 404 Not Found"

Это значит, что вы использовали неправильное имя пакета. Используйте:
```bash
npm install -g @tact-lang/compiler
```

### Ошибка: "EACCES: permission denied"

**Linux/macOS:**
```bash
sudo npm install -g @tact-lang/compiler
```

**Windows:**
Запустите командную строку от имени администратора.

### Ошибка: "command not found" после установки

Проверьте, что путь к npm глобальным пакетам в PATH:

**Windows:**
```
C:\Users\<Ваше_Имя>\AppData\Roaming\npm
```

**Linux/macOS:**
```bash
npm config get prefix
# Добавьте этот путь в PATH
```

### npm не установлен

Установите Node.js и npm:
- Windows/Linux/macOS: https://nodejs.org/

## После установки

Убедитесь, что compiler работает:

```bash
tact --version
tact --help
```

Если команда не найдена, перезапустите терминал или добавьте путь в PATH.

