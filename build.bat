@echo off
setlocal EnableExtensions

chcp 65001 >nul
title Building Disk Tree Analyzer...

:: --------------------------------------------------------
:: 1. Xac dinh thu muc project (khong de dau \ o cuoi)
:: --------------------------------------------------------
for %%I in ("%~dp0.") do set "ROOT=%%~fI"
set "OUT_DIR=%ROOT%\dist"
set "BUILD_DIR=%ROOT%\build"
set "ENTRY_FILE=%ROOT%\main.py"
set "REQUIREMENTS_FILE=%ROOT%\requirements.txt"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"

cd /d "%ROOT%"
if errorlevel 1 (
    echo [LOI] Khong the truy cap thu muc project:
    echo %ROOT%
    pause
    exit /b 1
)

echo.
echo ========================================================
echo             BUILD DISK TREE ANALYZER
echo ========================================================
echo.
echo [INFO] Project: %ROOT%

:: --------------------------------------------------------
:: Kiem tra cac file dau vao
:: --------------------------------------------------------
if not exist "%ENTRY_FILE%" (
    echo [LOI] Khong tim thay main.py!
    echo Duong dan: %ENTRY_FILE%
    pause
    exit /b 1
)

if not exist "%REQUIREMENTS_FILE%" (
    echo [LOI] Khong tim thay requirements.txt!
    echo Duong dan: %REQUIREMENTS_FILE%
    pause
    exit /b 1
)

:: --------------------------------------------------------
:: [1/4] Tao virtual environment neu chua ton tai
:: --------------------------------------------------------
echo.
echo [1/4] Khoi tao moi truong ao Python (.venv)...

if not exist "%PYTHON%" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [LOI] Khong tim thay lenh python trong PATH.
        echo Hay cai dat Python va bat tuy chon Add Python to PATH.
        pause
        exit /b 1
    )

    python -m venv "%ROOT%\.venv"
    if errorlevel 1 (
        echo [LOI] Khong the tao moi truong ao .venv!
        pause
        exit /b 1
    )
)

if not exist "%PYTHON%" (
    echo [LOI] Khong tim thay Python trong .venv sau khi khoi tao.
    pause
    exit /b 1
)

"%PYTHON%" --version
if errorlevel 1 (
    echo [LOI] Python trong .venv khong the khoi dong.
    pause
    exit /b 1
)

:: --------------------------------------------------------
:: [2/4] Cai dat dependencies
:: --------------------------------------------------------
echo.
echo [2/4] Cai dat thu vien tu requirements.txt...

"%PYTHON%" -m pip install --disable-pip-version-check --default-timeout=1000 --retries 10 -r "%REQUIREMENTS_FILE%"
if errorlevel 1 (
    echo [LOI] Khong the cai dat dependencies!
    pause
    exit /b 1
)

:: Dam bao PyInstaller da duoc cai dat
"%PYTHON%" -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller chua co trong moi truong. Dang cai dat...
    "%PYTHON%" -m pip install --disable-pip-version-check --default-timeout=1000 --retries 10 pyinstaller
    if errorlevel 1 (
        echo [LOI] Khong the cai dat PyInstaller!
        pause
        exit /b 1
    )
)

echo [INFO] PyInstaller version:
"%PYTHON%" -m PyInstaller --version
if errorlevel 1 (
    echo [LOI] Khong the chay PyInstaller.
    pause
    exit /b 1
)

:: Tao thu muc output neu chua ton tai
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
if errorlevel 1 (
    echo [LOI] Khong the tao thu muc dist!
    pause
    exit /b 1
)

:: --------------------------------------------------------
:: [3/4] Build EXE
:: Khong truyen --specpath de tranh loi quote voi duong dan
:: main.py duoc truyen tuong doi sau khi da cd vao ROOT.
:: --------------------------------------------------------
echo.
echo [3/4] Dong goi ung dung thanh file .exe...
echo [DEBUG] Python: "%PYTHON%"
echo [DEBUG] Entry file: "%ENTRY_FILE%"
echo [DEBUG] Working directory: "%CD%"
echo [DEBUG] Output: "%OUT_DIR%"
echo.

"%PYTHON%" -m PyInstaller --noconfirm --onefile --windowed --name "DiskTreeAnalyzer" --distpath "%OUT_DIR%" --workpath "%BUILD_DIR%" --clean main.py

if errorlevel 1 (
    echo.
    echo [LOI] Qua trinh dong goi PyInstaller that bai!
    echo Thu muc build duoc giu lai de kiem tra log:
    echo %BUILD_DIR%
    pause
    exit /b 1
)

:: Kiem tra file EXE thuc su duoc tao
if not exist "%OUT_DIR%\DiskTreeAnalyzer.exe" (
    echo [LOI] PyInstaller ket thuc nhung khong tim thay file EXE!
    echo Kiem tra thu muc: %OUT_DIR%
    pause
    exit /b 1
)

:: --------------------------------------------------------
:: [4/4] Don dep file tam sau khi build thanh cong
:: --------------------------------------------------------
echo.
echo [4/4] Don dep file tam sau khi build...

if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%ROOT%\DiskTreeAnalyzer.spec" del /f /q "%ROOT%\DiskTreeAnalyzer.spec"

echo.
echo ========================================================
echo                  BUILD THANH CONG!
echo ========================================================
echo.
echo File EXE:
echo %OUT_DIR%\DiskTreeAnalyzer.exe
echo.
echo Luu y: Hay thu chay EXE tren may Windows dich de kiem tra.
echo ========================================================
echo.
pause
endlocal
