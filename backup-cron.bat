@echo off
REM WordPress Backup Tool - Windows Cron Script
REM Uso: backup-cron.bat [config_file]
REM Ejemplo: backup-cron.bat .env.local

setlocal enabledelayedexpansion

REM Configuración
set "SCRIPT_DIR=%~dp0"
set "CONFIG_FILE=%~1"
if "%CONFIG_FILE%"=="" set "CONFIG_FILE=.env.local"

REM Crear timestamp para log
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "dt=%%a"
set "YY=%dt:~2,2%" & set "YYYY=%dt:~0,4%" & set "MM=%dt:~4,2%" & set "DD=%dt:~6,2%"
set "HH=%dt:~8,2%" & set "Min=%dt:~10,2%" & set "Sec=%dt:~12,2%"
set "LOG_FILE=%SCRIPT_DIR%logs\backup-%YYYY%%MM%%DD%-%HH%%Min%%Sec%.log"
set "LOCK_FILE=%SCRIPT_DIR%.backup.lock"

REM Crear directorio de logs si no existe
if not exist "%SCRIPT_DIR%logs" mkdir "%SCRIPT_DIR%logs"

echo ========================================== >> "%LOG_FILE%"
echo WordPress Backup Tool - Automated Backup >> "%LOG_FILE%"
echo ========================================== >> "%LOG_FILE%"
echo Script directory: %SCRIPT_DIR% >> "%LOG_FILE%"
echo Config file: %CONFIG_FILE% >> "%LOG_FILE%"
echo Log file: %LOG_FILE% >> "%LOG_FILE%"
echo Date/Time: %YYYY%-%MM%-%DD% %HH%:%Min%:%Sec% >> "%LOG_FILE%"

REM Verificar que no hay otro backup ejecutándose
if exist "%LOCK_FILE%" (
    echo [ERROR] Another backup process may be running >> "%LOG_FILE%"
    echo Check lock file: %LOCK_FILE% >> "%LOG_FILE%"
    exit /b 1
)

REM Crear lock file
echo %date% %time% > "%LOCK_FILE%"

REM Cambiar al directorio del script
cd /d "%SCRIPT_DIR%"

REM Verificar que existe el archivo de configuración
if not exist "%CONFIG_FILE%" (
    echo [ERROR] Configuration file '%CONFIG_FILE%' not found! >> "%LOG_FILE%"
    echo Available config files: >> "%LOG_FILE%"
    dir /b .env* >> "%LOG_FILE%" 2>nul
    del "%LOCK_FILE%" 2>nul
    exit /b 1
)

REM Verificar entorno virtual
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment... >> "%LOG_FILE%"
    call venv\Scripts\activate.bat
    echo [SUCCESS] Virtual environment activated >> "%LOG_FILE%"
) else (
    echo [WARNING] No virtual environment found. Using system Python. >> "%LOG_FILE%"
)

REM Verificar que wp-backup está disponible
wp-backup --help >nul 2>&1
if errorlevel 1 (
    echo [ERROR] wp-backup command not found! >> "%LOG_FILE%"
    echo Make sure the tool is installed: pip install -e . >> "%LOG_FILE%"
    del "%LOCK_FILE%" 2>nul
    exit /b 1
)

REM Mostrar info de configuración
for /f "tokens=2 delims==" %%a in ('findstr /b "WP_DOMAIN=" "%CONFIG_FILE%" 2^>nul') do set "WP_DOMAIN=%%a"
for /f "tokens=2 delims==" %%a in ('findstr /b "GDRIVE_FOLDER=" "%CONFIG_FILE%" 2^>nul') do set "GDRIVE_FOLDER=%%a"
if "%WP_DOMAIN%"=="" set "WP_DOMAIN=Unknown"
if "%GDRIVE_FOLDER%"=="" set "GDRIVE_FOLDER=WP-Backups"

echo [INFO] Backing up: %WP_DOMAIN% >> "%LOG_FILE%"
echo [INFO] Google Drive folder: %GDRIVE_FOLDER% >> "%LOG_FILE%"

REM Ejecutar backup
echo [INFO] Starting backup process... >> "%LOG_FILE%"

wp-backup backup --config "%CONFIG_FILE%" >> "%LOG_FILE%" 2>&1

if %errorlevel% equ 0 (
    echo [SUCCESS] Backup completed successfully! >> "%LOG_FILE%"
    
    REM Limpiar logs antiguos (más de 30 días)
    forfiles /p "%SCRIPT_DIR%logs" /m backup-*.log /d -30 /c "cmd /c del @path" 2>nul
    echo [INFO] Old log files cleaned up >> "%LOG_FILE%"
    
    del "%LOCK_FILE%" 2>nul
    exit /b 0
) else (
    echo [ERROR] Backup failed with exit code: %errorlevel% >> "%LOG_FILE%"
    del "%LOCK_FILE%" 2>nul
    exit /b %errorlevel%
)
