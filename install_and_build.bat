@echo off
chcp 65001 >nul
title Создание МенюГенератор.exe
color 0A

echo ========================================
echo    СОЗДАНИЕ ИСПОЛНЯЕМОГО ФАЙЛА
echo ========================================
echo.

REM Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден!
    echo Установите Python с https://python.org
    pause
    exit /b 1
)

echo ✓ Python найден
python --version

echo.
echo 1. Установка зависимостей...
echo.

pip install pandas openpyxl python-docx pyinstaller --quiet
if errorlevel 1 (
    echo ❌ Ошибка установки зависимостей!
    pause
    exit /b 1
)

echo ✓ Зависимости установлены

echo.
echo 2. Очистка предыдущих сборок...
echo.

if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist __pycache__ rmdir /s /q __pycache__
del *.spec 2>nul

echo ✓ Очистка выполнена

echo.
echo 3. Создание исполняемого файла...
echo.

pyinstaller --onefile --windowed ^
    --name "МенюГенератор" ^
    --add-data "canteen.db;." ^
    --add-data "ui;ui" ^
    --add-data "data;data" ^
    --add-data "generator;generator" ^
    --hidden-import=pandas ^
    --hidden-import=openpyxl ^
    --hidden-import=sqlite3 ^
    --hidden-import=docx ^
    main.py

if errorlevel 1 (
    echo.
    echo ❌ Ошибка сборки!
    pause
    exit /b 1
)

echo.
echo ========================================
echo ✅ Готово!
echo.
echo Исполняемый файл: dist\МенюГенератор.exe
echo.
echo Чтобы протестировать:
echo 1. Скопируйте dist\МенюГенератор.exe на рабочий стол
echo 2. Запустите его
echo 3. Проверьте работу программы
echo ========================================
echo.

REM Показать размер файла
if exist "dist\МенюГенератор.exe" (
    for %%F in ("dist\МенюГенератор.exe") do (
        set size=%%~zF
        set /a sizeMB=!size!/1024/1024
        echo Размер файла: !sizeMB! MB
    )
)

echo.
pause