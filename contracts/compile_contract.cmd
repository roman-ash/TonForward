@echo off
REM Компиляция Tact контракта Deal_simple.tact
REM Используйте этот файл в CMD (не PowerShell)

echo Compiling Deal_simple.tact...
tact --config tact.config.json

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✓ Compilation successful!
    echo.
    echo Output files should be in ./output/ directory
    echo.
) else (
    echo.
    echo ✗ Compilation failed
    echo.
)

