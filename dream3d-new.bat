::[Bat To Exe Converter]
::
::YAwzoRdxOk+EWAjk
::fBw5plQjdCuDJFWL8000Oh5VQVeGcmK5CdU=
::YAwzuBVtJxjWCl3EqQJgSA==
::ZR4luwNxJguZRRnk
::Yhs/ulQjdF+5
::cxAkpRVqdFKZSjk=
::cBs/ulQjdF+5
::ZR41oxFsdFKZSDk=
::eBoioBt6dFKZSDk=
::cRo6pxp7LAbNWATEpCI=
::egkzugNsPRvcWATEpCI=
::dAsiuh18IRvcCxnZtBJQ
::cRYluBh/LU+EWAnk
::YxY4rhs+aU+JeA==
::cxY6rQJ7JhzQF1fEqQJQ
::ZQ05rAF9IBncCkqN+0xwdVs0
::ZQ05rAF9IAHYFVzEqQJQ
::eg0/rx1wNQPfEVWB+kM9LVsJDGQ=
::fBEirQZwNQPfEVWB+kM9LVsJDGQ=
::cRolqwZ3JBvQF1fEqQJQ
::dhA7uBVwLU+EWDk=
::YQ03rBFzNR3SWATElA==
::dhAmsQZ3MwfNWATElA==
::ZQ0/vhVqMQ3MEVWAtB9wSA==
::Zg8zqx1/OA3MEVWAtB9wSA==
::dhA7pRFwIByZRRnk
::Zh4grVQjdCuDJEyU8EMkLVZQXgGDMTi+OrgV7/r6/OPKpl8YVe9sfLP/yLGPLaBAzgXHfII0mH9Cnas=
::YB416Ek+ZG8=
::
::
::978f952a14a936cc963da21a135fa983
@echo off
setlocal enabledelayedexpansion

:: ====== FIXED WORKING DIRECTORY ======
cd /d "%~dp0"
:: =====================================

:: ====== CONFIG ======
set "ENV_NAME=dream3d"
set "PYTHON_VERSION=3.9"
set "REQUIREMENTS=requirements.txt"
set "MAIN_SCRIPT=main.pyc"
:: =====================

:: ===== CARI CONDA SECARA DINAMIS =====
set "CONDA_PATH="
for %%G in (conda.bat) do (
    set "CONDA_PATH=%%~$PATH:G"
)
if not defined CONDA_PATH if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" (
    set "CONDA_PATH=%USERPROFILE%\miniconda3\condabin\conda.bat"
)
if not defined CONDA_PATH if exist "C:\Miniconda3\condabin\conda.bat" (
    set "CONDA_PATH=C:\Miniconda3\condabin\conda.bat"
)
if not defined CONDA_PATH if exist "C:\Anaconda3\condabin\conda.bat" (
    set "CONDA_PATH=C:\Anaconda3\condabin\conda.bat"
)
if not defined CONDA_PATH (
    echo [ERROR] conda.bat tidak ditemukan di PATH atau lokasi umum.
    echo Harap pastikan Miniconda sudah terinstal.
    pause
    exit /b
)
echo Conda terdeteksi.
:: =====================================

:: Activate base environment
call "%CONDA_PATH%" activate base
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
    echo.
    echo ====================================================
    echo [INFO] Environment "%ENV_NAME%" berhasil dibuat.
    echo 🔁 Sekarang TUTUP jendela ini, lalu JALANKAN ULANG file .exe ini.
    echo ====================================================
    echo.
    pause
    exit /b
)

:: Activate the dream3d environment
echo [INFO] Activating environment: %ENV_NAME%
call "%CONDA_PATH%" activate %ENV_NAME%

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

:: ========== LOGIN FIREBASE & RUN GUI ==========
:: Masukkan Firebase API Key
set "API_KEY=AIzaSyB6u5IjELRWKqDnW6xYicfk4kx4aF1sb5I"

:: Input email
set /p EMAIL=Enter email: 

:: Input password (disembunyikan)
for /f "delims=" %%p in ('powershell -Command "Read-Host 'Enter Password' -AsSecureString ^| ConvertFrom-SecureString"') do set ENCRYPTED_PASS=%%p
for /f "delims=" %%p in ('powershell -Command "([System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR((ConvertTo-SecureString '%ENCRYPTED_PASS%'))))"') do set PASSWORD=%%p

:: Jalankan PowerShell inline untuk login Firebase dan jalankan main.pyc jika berhasil
powershell -ExecutionPolicy Bypass -Command ^
    "$email = '%EMAIL%';" ^
    "$password = '%PASSWORD%';" ^
    "$apikey = '%API_KEY%';" ^
    "$body = @{ email = $email; password = $password; returnSecureToken = $true } | ConvertTo-Json -Compress;" ^
    "try {" ^
        "$response = Invoke-RestMethod -Uri \"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$apikey\" -Method Post -ContentType \"application/json\" -Body $body;" ^
        "if ($response.idToken) {" ^
            "Write-Host \"`n✅ Login berhasil: $($response.email)\";" ^
            "if (Test-Path '%MAIN_SCRIPT%') {" ^
                "Write-Host '[INFO] Menjalankan DREAM3D GUI...';" ^
                "Start-Process -NoNewWindow python '%MAIN_SCRIPT%'" ^
            "} else {" ^
                "Write-Host '[ERROR] File %MAIN_SCRIPT% tidak ditemukan.'; exit 1" ^
            "}" ^
        "} else {" ^
            "Write-Host \"`n❌ Login gagal: Token tidak diterima.\"; exit 1;" ^
        "}" ^
    "} catch {" ^
        "Write-Host \"`n❌ Login gagal: $($_.ErrorDetails.error.message)\";" ^
        "exit 1;" ^
    "}"

:: Tangkap exit code dari PowerShell
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Login gagal. Aplikasi ditutup.
    timeout /t 3 >nul
    exit /b
)

:: Optional: pause here (boleh dihapus kalau tidak perlu)
pause
