@echo off
setlocal enabledelayedexpansion

:: ====== CONFIG ======
set "ENV_NAME=dream3d"
set "PYTHON_VERSION=3.9"
set "REQUIREMENTS=requirements.txt"
set "MAIN_SCRIPT=main.py"
set "CONDA_PATH=C:\ProgramData\miniconda3\condabin\conda.bat"
:: =====================

:: Check if Conda is installed
if not exist "%CONDA_PATH%" (
    echo [ERROR] Miniconda/Anaconda not found at: %CONDA_PATH%
    echo Please install Miniconda first!
    pause
    exit /b
)

echo [INFO] Conda found at: %CONDA_PATH%

:: Activate base environment
call "%CONDA_PATH%" activate base

:: Refresh Conda env list
call conda info --envs >nul

:: Check if the environment exists
echo [INFO] Checking for Conda environment: %ENV_NAME%
for /f "delims=" %%e in ('conda info --envs ^| findstr /R /C:"%ENV_NAME%"') do (
    set "ENV_EXISTS=1"
)
if not defined ENV_EXISTS (
    echo [WARNING] Environment "%ENV_NAME%" not found.
    echo [INFO] Creating environment "%ENV_NAME%" with Python %PYTHON_VERSION%...
    call conda create --yes --name %ENV_NAME% python=%PYTHON_VERSION%
    call conda info --envs >nul
    echo [INFO] Environment created.
    echo Please re-run this script to continue installation and launch the GUI.
    pause
    exit /b
)

if errorlevel 1 (
    echo [WARNING] Environment "%ENV_NAME%" not found.
    echo [INFO] Creating environment "%ENV_NAME%" with Python %PYTHON_VERSION%...
    call conda create --yes --name %ENV_NAME% python=%PYTHON_VERSION%
    echo [INFO] Environment created.
    echo Please re-run this script to continue installation and launch the GUI.
    pause
    exit /b
)

:: Activate the dream3d environment
echo [INFO] Activating environment: %ENV_NAME%
call "%CONDA_PATH%" activate %ENV_NAME% && set PYTHONIOENCODING=utf-8

:: Check if key library is installed
echo [INFO] Checking if PyQt5 is already installed...
pip show PyQt5 >nul 2>&1

:: Install requirements
if errorlevel 1 (
    echo [INFO] PyQt5 not found. Installing required packages from %REQUIREMENTS%...
    if exist "%REQUIREMENTS%" (
        pip install -r "%REQUIREMENTS%"
    ) else (
        echo [ERROR] File "%REQUIREMENTS%" not found!
        pause
        exit /b
    )
) else (
    echo [INFO] PyQt5 already installed. Skipping requirements installation.
)

:: Run the GUI
if exist "%MAIN_SCRIPT%" (
    echo [INFO] Running GUI: %MAIN_SCRIPT%...
    python "%MAIN_SCRIPT%"
) else (
    echo [ERROR] File "%MAIN_SCRIPT%" not found!
    pause
    exit /b
)

pause