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
    log_info "Make sure the tool is installed:"
    log_info "  pip install -e ."
    exit 1
fi

# Cargar configuración para mostrar info
if [ -f "$CONFIG_FILE" ]; then
    WP_DOMAIN=$(grep "^WP_DOMAIN=" "$CONFIG_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "Unknown")
    GDRIVE_FOLDER=$(grep "^GDRIVE_FOLDER=" "$CONFIG_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "WP-Backups")
    log_info "Backing up: $WP_DOMAIN"
    log_info "Google Drive folder: $GDRIVE_FOLDER"
fi

# Ejecutar backup
log_info "Starting backup process..."

# Usar timeout para evitar que se cuelgue indefinidamente (30 minutos máximo)
if timeout 1800 wp-backup backup --config-file "$CONFIG_FILE" >> "$LOG_FILE" 2>&1; then
    log_success "Backup completed successfully!"
    
    # Opcional: Limpiar logs antiguos (mantener últimos 30 días)
    find "$SCRIPT_DIR/logs" -name "backup-*.log" -mtime +30 -delete 2>/dev/null || true
    log_info "Old log files cleaned up"
    
    exit 0
else
    EXIT_CODE=$?
    log_error "Backup failed with exit code: $EXIT_CODE"
    
    # Mostrar las últimas líneas del log para debugging
    log_error "Last 10 lines of output:"
    tail -n 10 "$LOG_FILE" | while read line; do
        log_error "  $line"
    done
    
    exit $EXIT_CODE
fi
