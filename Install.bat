@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul

:: ============================================================================
:: UmeAiRT ComfyUI — Auto-Installer
:: Double-click this file to install ComfyUI with all dependencies.
:: No prerequisites required — uv handles everything.
:: ============================================================================

title UmeAiRT ComfyUI Installer
echo.
echo ============================================================================
echo           UmeAiRT ComfyUI — Auto-Installer
echo ============================================================================
echo.

:: Script location (where bootstrap tools live)
set "ScriptDir=%~dp0"
if "%ScriptDir:~-1%"=="\" set "ScriptDir=%ScriptDir:~0,-1%"

:: ============================================================================
:: Step 1: Ask for installation path
:: ============================================================================
set "DefaultInstall=%USERPROFILE%\ComfyUI"
echo Where would you like to install ComfyUI?
echo   Default: %DefaultInstall%
echo.
set /p "InstallPath=Install path (Enter for default): "
if "%InstallPath%"=="" set "InstallPath=%DefaultInstall%"

:: Trim trailing backslash
if "%InstallPath:~-1%"=="\" set "InstallPath=%InstallPath:~0,-1%"

:: Create if it doesn't exist
if not exist "%InstallPath%" (
    mkdir "%InstallPath%"
    if !errorlevel! neq 0 (
        echo [ERROR] Could not create directory: %InstallPath%
        pause
        exit /b 1
    )
)

echo.
echo [INFO] Installation path: %InstallPath%
echo.

:: ============================================================================
:: Step 1.5: Ask for environment type (venv or conda)
:: ============================================================================
set "InstallType=venv"
echo What type of Python environment do you want to use?
echo   1: venv (Default, Recommended - isolated, fast)
echo   2: conda (Isolated local prefix via Miniconda)
echo.
set /p "EnvChoice=Choice (1 or 2, Enter for 1): "

if "%EnvChoice%"=="2" (
    set "InstallType=conda"
) else (
    set "InstallType=venv"
)

echo.
echo [INFO] Environment type: %InstallType%
echo.

:: ============================================================================
:: Step 1.6: Ask for custom nodes bundle
:: ============================================================================
set "NodeTier=umeairt"
echo Select custom nodes bundle:
echo   1: Minimal   - ComfyUI-Manager only
echo   2: UmeAiRT   - Manager + UmeAiRT Toolkit (Default, Recommended)
echo   3: Full      - All 34 nodes
echo.
set /p "NodeChoice=Choice (1, 2 or 3, Enter for 2): "

if "%NodeChoice%"=="1" (
    set "NodeTier=minimal"
) else if "%NodeChoice%"=="3" (
    set "NodeTier=full"
) else (
    set "NodeTier=umeairt"
)

echo.
echo [INFO] Nodes bundle: %NodeTier%
echo.

:: ============================================================================
:: Step 2: Ensure uv is available (standalone binary, no prerequisites)
:: ============================================================================
set "UV_DIR=%InstallPath%\scripts\uv"
set "UV_EXE=%UV_DIR%\uv.exe"

if not exist "%UV_EXE%" (
    echo [INFO] Downloading uv package manager...
    mkdir "%UV_DIR%" 2>nul

    :: curl and tar are available natively on Windows 10/11
    curl -LsSf -o "%TEMP%\uv-installer.zip" ^
        "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to download uv. Check your internet connection.
        pause
        exit /b 1
    )

    tar -xf "%TEMP%\uv-installer.zip" -C "%UV_DIR%"
    del "%TEMP%\uv-installer.zip" 2>nul
    echo [INFO] uv installed.
) else (
    echo [INFO] uv already available.
)

:: ============================================================================
:: Step 3: Create bootstrap venv (uv auto-downloads Python 3.11-3.13 if needed)
:: ============================================================================
set "VENV_PATH=%InstallPath%\scripts\venv"
set "VENV_PY=%VENV_PATH%\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [INFO] Creating Python environment...
    "%UV_EXE%" venv "%VENV_PATH%" --python ">=3.11,<3.14" --python-preference only-system --seed --link-mode copy
    if !errorlevel! neq 0 (
        echo [INFO] No compatible system Python found, downloading...
        "%UV_EXE%" venv "%VENV_PATH%" --python ">=3.11,<3.14" --seed --link-mode copy
        if !errorlevel! neq 0 (
            echo [ERROR] Failed to create Python environment.
            pause
            exit /b 1
        )
    )
    echo [INFO] Python environment ready.
) else (
    echo [INFO] Python environment already exists.
)

:: ============================================================================
:: Step 4: Install the installer package into the venv
:: ============================================================================
echo [INFO] Installing umeairt-comfyui-installer...
"%UV_EXE%" pip install -e "%ScriptDir%" --python "%VENV_PY%" --quiet
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install umeairt-comfyui-installer.
    pause
    exit /b 1
)

:: ============================================================================
:: Step 5: Launch the installer CLI
:: ============================================================================
echo [INFO] Starting installation...
echo.
"%VENV_PY%" -m src.cli install --path "%InstallPath%" --type "%InstallType%" --nodes "%NodeTier%"

pause
