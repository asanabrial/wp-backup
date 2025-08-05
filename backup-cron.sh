#!/bin/bash

# WordPress Backup Tool - Cron Script
# Uso: ./backup-cron.sh [config_file]
# Ejemplo: ./backup-cron.sh .env.local

set -e  # Salir si cualquier comando falla

# Configuración
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${1:-.env.local}"
LOG_FILE="$SCRIPT_DIR/logs/backup-$(date +%Y%m%d-%H%M%S).log"
LOCK_FILE="$SCRIPT_DIR/.backup.lock"

# Colores para logs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función de logging
log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

log_error() {
    log "${RED}[ERROR]${NC} $1"
}

log_success() {
    log "${GREEN}[SUCCESS]${NC} $1"
}

log_info() {
    log "${BLUE}[INFO]${NC} $1"
}

log_warning() {
    log "${YELLOW}[WARNING]${NC} $1"
}

# Función de limpieza al salir
cleanup() {
    if [ -f "$LOCK_FILE" ]; then
        rm -f "$LOCK_FILE"
        log_info "Lock file removed"
    fi
}

# Configurar trap para limpieza
trap cleanup EXIT INT TERM

# Verificar que no hay otro backup ejecutándose
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        log_error "Another backup process is running (PID: $LOCK_PID)"
        exit 1
    else
        log_warning "Stale lock file found, removing..."
        rm -f "$LOCK_FILE"
    fi
fi

# Crear lock file
echo $$ > "$LOCK_FILE"

# Crear directorio de logs si no existe
mkdir -p "$SCRIPT_DIR/logs"

log_info "=========================================="
log_info "WordPress Backup Tool - Automated Backup"
log_info "=========================================="
log_info "Script directory: $SCRIPT_DIR"
log_info "Config file: $CONFIG_FILE"
log_info "Log file: $LOG_FILE"

# Cambiar al directorio del script
cd "$SCRIPT_DIR"

# Verificar que existe el archivo de configuración
if [ ! -f "$CONFIG_FILE" ]; then
    log_error "Configuration file '$CONFIG_FILE' not found!"
    log_info "Available config files:"
    ls -la .env* 2>/dev/null || log_info "No .env files found"
    exit 1
fi

# Función para verificar autenticación de Google Drive
check_google_auth() {
    log_info "Checking Google Drive authentication..."
    
    # Verificar si existe token
    if [ ! -f "token.pickle" ]; then
        log_error "Google Drive token not found!"
        log_info "You need to run OAuth setup first:"
        log_info "  wp-backup test"
        log_info "This will complete the OAuth flow and create token.pickle"
        return 1
    fi
    
    # Verificar si el token funciona (test rápido sin output)
    # El comando test no acepta --config-file, usa .env.local por defecto
    if timeout 60 wp-backup test >/dev/null 2>&1; then
        log_success "Google Drive authentication verified"
        return 0
    else
        log_warning "Google Drive token may be expired or invalid"
        log_info "Try running: wp-backup test"
        return 1
    fi
}

# Verificar entorno virtual
if [ -d "venv" ]; then
    log_info "Activating virtual environment..."
    source venv/bin/activate
    log_success "Virtual environment activated"
else
    log_warning "No virtual environment found (venv/). Using system Python."
fi

# Verificar que wp-backup está disponible
if ! command -v wp-backup &> /dev/null; then
    log_error "wp-backup command not found!"
    log_info "Attempting to install/reinstall..."
    
    # Intentar instalar automáticamente
    if pip install -e . >> "$LOG_FILE" 2>&1; then
        log_success "wp-backup installed successfully"
    else
        log_error "Installation failed. Manual steps required:"
        log_info "  1. source venv/bin/activate"
        log_info "  2. pip install --upgrade pip"
        log_info "  3. pip install -e ."
        exit 1
    fi
fi

# Verificar instalación
# Note: wp-backup no tiene --version, usamos --help para verificar
if wp-backup --help >/dev/null 2>&1; then
    log_success "wp-backup command is working properly"
    WP_BACKUP_VERSION="installed"
else
    log_error "wp-backup command is not working"
    WP_BACKUP_VERSION="error"
fi
log_info "wp-backup status: $WP_BACKUP_VERSION"

# Si hay problemas, intentar obtener más información
if [ "$WP_BACKUP_VERSION" = "error" ]; then
    log_warning "wp-backup command has issues"
    log_info "Checking installation details..."
    
    # Verificar si el comando existe
    WP_BACKUP_PATH=$(which wp-backup 2>/dev/null || echo "not found")
    log_info "wp-backup path: $WP_BACKUP_PATH"
    
    log_info "Attempting reinstallation..."
    if pip install -e . >> "$LOG_FILE" 2>&1; then
        log_success "Reinstallation completed"
    else
        log_error "Reinstallation failed"
        exit 1
    fi
fi

# Cargar configuración para mostrar info
if [ -f "$CONFIG_FILE" ]; then
    WP_DOMAIN=$(grep "^WP_DOMAIN=" "$CONFIG_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "Unknown")
    GDRIVE_FOLDER=$(grep "^GDRIVE_FOLDER=" "$CONFIG_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "WP-Backups")
    log_info "Backing up: $WP_DOMAIN"
    log_info "Google Drive folder: $GDRIVE_FOLDER"
fi

# Verificar autenticación de Google Drive antes del backup
if ! check_google_auth; then
    log_error "Cannot proceed without valid Google Drive authentication"
    exit 1
fi

# Ejecutar backup
log_info "Starting backup process..."

# Verificar si ya existe un token válido
if [ ! -f "token.pickle" ]; then
    log_warning "No Google Drive token found. Manual OAuth may be required."
    log_info "Run 'wp-backup test' manually first to complete OAuth setup."
fi

# Detectar el parámetro correcto para configuración
BACKUP_CMD="wp-backup backup"
if [ "$CONFIG_FILE" != ".env.local" ]; then
    # Si no es el archivo por defecto, intentar con --config-file
    log_info "Using config file: $CONFIG_FILE"
    BACKUP_CMD="$BACKUP_CMD --config-file $CONFIG_FILE"
else
    log_info "Using default config file (.env.local)"
fi

# Usar timeout para evitar que se cuelgue indefinidamente (10 minutos máximo para cron)
# Ejecutar en modo no interactivo para evitar prompts
export PYTHONUNBUFFERED=1
log_info "Timeout set to 10 minutes for automated execution"
log_info "Command: $BACKUP_CMD"

if timeout 600 $BACKUP_CMD </dev/null >> "$LOG_FILE" 2>&1; then
    log_success "Backup completed successfully!"
    
    # Opcional: Limpiar logs antiguos (mantener últimos 30 días)
    find "$SCRIPT_DIR/logs" -name "backup-*.log" -mtime +30 -delete 2>/dev/null || true
    log_info "Old log files cleaned up"
    
    exit 0
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        log_error "Backup timed out after 10 minutes"
        log_info "This usually means:"
        log_info "  • OAuth authentication is required (run 'wp-backup test' manually)"
        log_info "  • Process is waiting for user input"
        log_info "  • Large backup taking too long"
    else
        log_error "Backup failed with exit code: $EXIT_CODE"
    fi
    
    # Mostrar las últimas líneas del log para debugging
    log_error "Last 15 lines of output:"
    tail -n 15 "$LOG_FILE" | while read line; do
        log_error "  $line"
    done
    
    exit $EXIT_CODE
fi
