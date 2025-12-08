#!/bin/bash

# Скрипт для компиляции Tact контракта Deal
# Требует установленный Tact compiler: https://tact-lang.org/

echo "Compiling Deal.tact contract..."

# Проверяем наличие Tact compiler
if ! command -v tact &> /dev/null; then
    echo "Error: Tact compiler not found."
    echo ""
    echo "Install it using one of these methods:"
    echo "1. npm install -g @tact-lang/compiler"
    echo "2. Download binary from https://github.com/tact-lang/tact/releases"
    echo "3. Use npx: npx @tact-lang/compiler compile Deal.tact"
    exit 1
fi

# Компилируем контракт
tact compile Deal.tact

if [ $? -eq 0 ]; then
    echo "✓ Contract compiled successfully"
    echo ""
    echo "Next steps:"
    echo "1. Find the compiled code in Deal.code.boc"
    echo "2. Convert to base64: base64 -i Deal.code.boc > Deal.code.b64"
    echo "3. Copy the content of Deal.code.b64 to DEAL_CONTRACT_CODE_B64 env variable"
else
    echo "✗ Compilation failed"
    exit 1
fi

