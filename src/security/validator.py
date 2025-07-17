"""
Configuration validation and sanitization
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse


class ConfigValidator:
    """Validación exhaustiva y sanitización de configuración"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_full_config(self, config: Dict[str, Any]) -> bool:
        """Valida configuración completa"""
        self.errors.clear()
        self.warnings.clear()
        
        # Validar cada sección
        self._validate_wordpress_config(config.get('wordpress', {}))
        self._validate_google_drive_config(config.get('google_drive', {}))
        self._validate_sharing_config(config.get('sharing', {}))
        
        if config.get('database'):
            self._validate_database_config(config['database'])
        
        return len(self.errors) == 0
    
    def _validate_wordpress_config(self, wp_config: Dict[str, Any]) -> None:
        """Valida configuración de WordPress"""
        # Validar dominio
        domain = wp_config.get('domain')
        if not domain:
            self.errors.append("WordPress domain is required")
        elif not self._is_valid_domain(domain):
            self.errors.append(f"Invalid WordPress domain format: {domain}")
        elif domain in ['example.com', 'localhost', 'test.com']:
            self.warnings.append(f"WordPress domain looks like a placeholder: {domain}")
        
        # Validar ruta de WordPress
        wp_path = wp_config.get('path')
        if not wp_path:
            self.errors.append("WordPress path is required")
        elif not self._is_safe_path(str(wp_path)):
            self.errors.append(f"WordPress path appears unsafe: {wp_path}")
        
        # Validar directorio de backup
        backup_dir = wp_config.get('backup_dir')
        if backup_dir and not self._is_safe_path(str(backup_dir)):
            self.errors.append(f"Backup directory appears unsafe: {backup_dir}")
    
    def _validate_google_drive_config(self, gdrive_config: Dict[str, Any]) -> None:
        """Valida configuración de Google Drive"""
        # Validar carpeta de Google Drive
        folder = gdrive_config.get('folder')
        if not folder:
            self.errors.append("Google Drive folder is required")
        elif not self._is_valid_gdrive_folder(folder):
            self.errors.append(f"Invalid Google Drive folder path: {folder}")
        
        # Validar archivo de credenciales
        creds_file = gdrive_config.get('credentials_file')
        if not creds_file:
            self.errors.append("Google Drive credentials file is required")
        elif not Path(creds_file).exists():
            self.warnings.append(f"Google Drive credentials file not found: {creds_file}")
        
        # Validar días de retención
        retention_days = gdrive_config.get('retention_days')
        if retention_days is not None:
            if not isinstance(retention_days, int) or retention_days < 1 or retention_days > 365:
                self.errors.append("Retention days must be between 1 and 365")
    
    def _validate_sharing_config(self, sharing_config: Dict[str, Any]) -> None:
        """Valida configuración de compartir"""
        # Validar emails
        emails = sharing_config.get('emails', [])
        if emails:
            for email in emails:
                if not self._is_valid_email(email):
                    self.errors.append(f"Invalid email format: {email}")
        
        # Validar rol
        role = sharing_config.get('role')
        if role and role not in ['reader', 'writer']:
            self.errors.append(f"Invalid sharing role: {role}. Must be 'reader' or 'writer'")
        
        # Validar make_public
        make_public = sharing_config.get('make_public')
        if make_public is not None and not isinstance(make_public, bool):
            self.errors.append("make_public must be a boolean value")
    
    def _validate_database_config(self, db_config: Dict[str, Any]) -> None:
        """Valida configuración de base de datos"""
        required_fields = ['host', 'name', 'user']
        for field in required_fields:
            if not db_config.get(field):
                self.errors.append(f"Database {field} is required")
        
        # Validar host
        host = db_config.get('host')
        if host and not self._is_valid_db_host(host):
            self.warnings.append(f"Database host format might be invalid: {host}")
        
        # Validar nombre de base de datos
        db_name = db_config.get('name')
        if db_name and not self._is_valid_db_name(db_name):
            self.errors.append(f"Invalid database name format: {db_name}")
    
    def _is_valid_domain(self, domain: str) -> bool:
        """Valida formato de dominio"""
        domain_pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        return bool(re.match(domain_pattern, domain))
    
    def _is_valid_email(self, email: str) -> bool:
        """Valida formato de email"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, email))
    
    def _is_safe_path(self, path: str) -> bool:
        """Valida que una ruta sea segura"""
        # Verificar que no contenga caracteres peligrosos
        dangerous_patterns = [
            r'\.\.',  # Path traversal
            r'[<>"|*?]',  # Caracteres inválidos en Windows
            r'^[/\\]+$',  # Solo separadores
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, path):
                return False
        
        # Verificar que no sea una ruta de sistema crítica
        critical_paths = [
            '/bin', '/boot', '/dev', '/etc', '/lib', '/proc', '/root', '/sbin', '/sys',
            'C:\\Windows', 'C:\\Program Files', 'C:\\System32'
        ]
        
        normalized_path = os.path.normpath(path).lower()
        for critical in critical_paths:
            if normalized_path.startswith(critical.lower()):
                return False
        
        return True
    
    def _is_valid_gdrive_folder(self, folder: str) -> bool:
        """Valida formato de carpeta de Google Drive"""
        # No debe estar vacío
        if not folder.strip():
            return False
        
        # No debe contener caracteres inválidos
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        if any(char in folder for char in invalid_chars):
            return False
        
        # No debe empezar o terminar con espacios o puntos
        if folder.startswith((' ', '.')) or folder.endswith((' ', '.')):
            return False
        
        return True
    
    def _is_valid_db_host(self, host: str) -> bool:
        """Valida formato de host de base de datos"""
        # Puede ser IP, dominio o localhost
        if host in ['localhost', '127.0.0.1', '::1']:
            return True
        
        # Validar IP
        ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        if re.match(ip_pattern, host):
            return True
        
        # Validar dominio
        return self._is_valid_domain(host)
    
    def _is_valid_db_name(self, db_name: str) -> bool:
        """Valida nombre de base de datos"""
        # Patrón típico para nombres de BD MySQL
        pattern = r'^[a-zA-Z0-9_][a-zA-Z0-9_$]*$'
        return bool(re.match(pattern, db_name)) and len(db_name) <= 64
    
    def sanitize_config_for_logging(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitiza configuración para logging seguro"""
        sanitized = {}
        
        for key, value in config.items():
            if isinstance(value, dict):
                sanitized[key] = self.sanitize_config_for_logging(value)
            elif key.lower() in ['password', 'secret', 'token', 'key']:
                sanitized[key] = "***"
            elif isinstance(value, str) and '@' in value and '.' in value:
                # Posible email - enmascarar parcialmente
                if self._is_valid_email(value):
                    parts = value.split('@')
                    sanitized[key] = f"***@{parts[1]}"
                else:
                    sanitized[key] = value
            else:
                sanitized[key] = value
        
        return sanitized
    
    def get_validation_report(self) -> Dict[str, List[str]]:
        """Obtiene reporte de validación"""
        return {
            'errors': self.errors.copy(),
            'warnings': self.warnings.copy(),
            'is_valid': len(self.errors) == 0
        }
    
    def validate_environment_security(self) -> List[str]:
        """Valida aspectos de seguridad del entorno"""
        security_issues = []
        
        # Verificar archivos de configuración
        sensitive_files = ['.env', '.env.local', 'config/gdrive-credentials.json', 'token.pickle']
        
        for file_path in sensitive_files:
            if Path(file_path).exists():
                # Verificar permisos (en sistemas Unix)
                if hasattr(os, 'stat'):
                    try:
                        stat_info = os.stat(file_path)
                        # Verificar que no sea legible por otros
                        if stat_info.st_mode & 0o044:  # Otros tienen permisos de lectura
                            security_issues.append(f"File {file_path} is readable by others")
                    except OSError:
                        pass
        
        # Verificar variables de entorno sensibles
        sensitive_env_vars = ['DB_PASSWORD', 'GDRIVE_CLIENT_SECRET', 'API_KEY']
        for var in sensitive_env_vars:
            if var in os.environ:
                security_issues.append(f"Sensitive environment variable {var} is set globally")
        
        return security_issues
