"""
Secure configuration management without hardcoded sensitive data
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pydantic import BaseModel, Field, field_validator

from ..security.secrets import SecretManager
from ..security.validator import ConfigValidator


@dataclass
class DatabaseCredentials:
    """Database credentials"""
    host: str
    name: str
    user: str
    password: str


class WordPressConfig(BaseModel):
    """WordPress configuration - NO hardcoded values"""
    domain: str = Field(..., description="WordPress domain (required)")
    path: Path = Field(..., description="WordPress installation path")
    backup_dir: Path = Field(default=Path("/tmp/wp-backup"), description="Temporary backup directory")

    @field_validator('domain')
    @classmethod
    def validate_domain(cls, v):
        if not v or v in ['example.com', 'localhost', 'test.com']:
            raise ValueError("WordPress domain must be properly configured (not a placeholder)")
        return v

    @field_validator('path')
    @classmethod
    def validate_path(cls, v):
        if not str(v) or str(v) in ['/var/www/example.com', '/example/path']:
            raise ValueError("WordPress path must be properly configured (not a placeholder)")
        return v


class GoogleDriveConfig(BaseModel):
    """Google Drive configuration"""
    folder: str = Field(..., description="Google Drive backup folder path")
    credentials_file: Path = Field(..., description="OAuth credentials JSON file path")
    retention_days: int = Field(default=7, ge=1, le=365, description="Days to retain backups")

    @field_validator('folder')
    @classmethod
    def validate_folder(cls, v):
        if not v or v in ['backup/example.com', 'test/backup']:
            raise ValueError("Google Drive folder must be properly configured")
        return v


class SharingConfig(BaseModel):
    """Sharing configuration"""
    emails: List[str] = Field(default_factory=list, description="Emails to share with")
    role: str = Field(default="writer", pattern="^(reader|writer)$", description="Sharing role")
    make_public: bool = Field(default=False, description="Make backup folder public")

    @field_validator('emails')
    @classmethod
    def validate_emails(cls, v):
        if not v:
            return v
        
        validator = ConfigValidator()
        for email in v:
            if not validator._is_valid_email(email):
                raise ValueError(f"Invalid email format: {email}")
        return v


class Config(BaseModel):
    """Main application configuration - secure and validated"""
    wordpress: WordPressConfig
    google_drive: GoogleDriveConfig
    sharing: SharingConfig
    database: Optional[DatabaseCredentials] = None
    environment: str = Field(default="production", pattern="^(development|staging|production)$")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "validate_assignment": True}


class SecureConfigLoader:
    """Secure configuration loader with validation"""
    
    def __init__(self):
        self.secret_manager = SecretManager()
        self.validator = ConfigValidator()
    
    def load_config(self, config_file: Optional[str] = None) -> Config:
        """Load configuration securely without hardcoded defaults"""
        
        # Si se especifica archivo personalizado, cargarlo
        if config_file and Path(config_file).exists():
            self._load_custom_env_file(config_file)
        
        # Construir configuración desde secretos seguros
        config_data = self._build_config_data()
        
        # Validar configuración
        if not self.validator.validate_full_config(config_data):
            validation_report = self.validator.get_validation_report()
            errors = validation_report['errors']
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
        
        # Crear instancia de configuración
        try:
            return Config(**config_data)
        except Exception as e:
            # Enmascarar datos sensibles en el error
            masked_error = self.secret_manager.mask_sensitive_data(str(e))
            raise ValueError(f"Configuration error: {masked_error}")
    
    def _load_custom_env_file(self, config_file: str) -> None:
        """Carga archivo de configuración personalizado"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip().strip('\'"')
        except Exception as e:
            raise ValueError(f"Error loading config file {config_file}: {e}")
    
    def _build_config_data(self) -> Dict[str, Any]:
        """Construye datos de configuración desde fuentes seguras"""
        
        config_data = {
            "wordpress": self._get_wordpress_config(),
            "google_drive": self._get_google_drive_config(),
            "sharing": self._get_sharing_config(),
        }
        
        # Base de datos opcional
        db_config = self._get_database_config()
        if db_config:
            config_data["database"] = db_config
        
        # Entorno
        environment = self.secret_manager.get_secret("ENVIRONMENT") or "production"
        config_data["environment"] = environment
        
        return config_data
    
    def _get_wordpress_config(self) -> Dict[str, Any]:
        """Obtiene configuración de WordPress"""
        domain = self.secret_manager.get_secret(
            "WP_DOMAIN", 
            "Enter WordPress domain (e.g., mysite.com)"
        )
        if not domain:
            raise ValueError("WordPress domain is required")
        
        wp_path = self.secret_manager.get_secret(
            "WP_PATH",
            "Enter WordPress installation path (e.g., /var/www/mysite.com)"
        )
        if not wp_path:
            raise ValueError("WordPress path is required")
        
        backup_dir = self.secret_manager.get_secret("BACKUP_DIR") or "/tmp/wp-backup"
        
        return {
            "domain": domain,
            "path": Path(wp_path),
            "backup_dir": Path(backup_dir),
        }
    
    def _get_google_drive_config(self) -> Dict[str, Any]:
        """Obtiene configuración de Google Drive"""
        folder = self.secret_manager.get_secret(
            "GDRIVE_FOLDER",
            "Enter Google Drive folder path (e.g., backup/mysite.com)"
        )
        if not folder:
            raise ValueError("Google Drive folder is required")
        
        credentials_file = self.secret_manager.get_secret(
            "GDRIVE_CREDENTIALS_FILE",
            "Enter Google Drive credentials file path (e.g., config/gdrive-credentials.json)"
        ) or "config/gdrive-credentials.json"
        
        retention_days = int(self.secret_manager.get_secret("RETENTION_DAYS") or "7")
        
        return {
            "folder": folder,
            "credentials_file": Path(credentials_file),
            "retention_days": retention_days,
        }
    
    def _get_sharing_config(self) -> Dict[str, Any]:
        """Obtiene configuración de compartir"""
        share_emails_str = self.secret_manager.get_secret("SHARE_EMAILS") or ""
        share_emails = [email.strip() for email in share_emails_str.split(",") if email.strip()]
        
        share_role = self.secret_manager.get_secret("SHARE_ROLE") or "writer"
        make_public_str = self.secret_manager.get_secret("MAKE_PUBLIC") or "false"
        make_public = make_public_str.lower() in ["true", "1", "yes"]
        
        return {
            "emails": share_emails,
            "role": share_role,
            "make_public": make_public,
        }
    
    def _get_database_config(self) -> Optional[Dict[str, str]]:
        """Obtiene configuración de base de datos si está disponible"""
        required_keys = ["DB_HOST", "DB_NAME", "DB_USER"]
        
        # Verificar si todas las claves requeridas están disponibles
        db_values = {}
        for key in required_keys:
            value = self.secret_manager.get_secret(key)
            if not value:
                return None  # Si falta alguna, no usar configuración manual de BD
            db_values[key.lower().replace("db_", "")] = value
        
        # Password puede estar vacío
        password = self.secret_manager.get_secret("DB_PASSWORD") or ""
        db_values["password"] = password
        
        return db_values
    
    def create_secure_env_template(self) -> None:
        """Crea un template seguro para configuración"""
        template_config = {
            "WP_DOMAIN": "WordPress domain (e.g., mysite.com)",
            "WP_PATH": "WordPress installation path (e.g., /var/www/mysite.com)",
            "BACKUP_DIR": "Temporary backup directory (optional, default: /tmp/wp-backup)",
            "GDRIVE_FOLDER": "Google Drive backup folder (e.g., backup/mysite.com)",
            "GDRIVE_CREDENTIALS_FILE": "OAuth credentials file (default: config/gdrive-credentials.json)",
            "RETENTION_DAYS": "Days to retain backups (default: 7)",
            "SHARE_EMAILS": "Comma-separated emails to share with (optional)",
            "SHARE_ROLE": "Sharing role: reader or writer (default: writer)",
            "MAKE_PUBLIC": "Make backup folder public: true or false (default: false)",
            "ENVIRONMENT": "Environment: development, staging, or production (default: production)",
        }
        
        self.secret_manager.create_env_template(template_config, ".env.local.example")
        print("✅ Created .env.local.example template")
        print("💡 Copy to .env.local and fill in your values")
    
    def print_config_summary(self, config: Config) -> None:
        """Imprime resumen de configuración de forma segura"""
        sanitized = self.validator.sanitize_config_for_logging(config.model_dump())
        
        print("\n=== CONFIGURATION SUMMARY ===")
        print(f"WordPress:")
        print(f"  • Domain: {sanitized['wordpress']['domain']}")
        print(f"  • Path: {sanitized['wordpress']['path']}")
        print(f"  • Backup dir: {sanitized['wordpress']['backup_dir']}")
        
        print(f"\nGoogle Drive:")
        print(f"  • Folder: {sanitized['google_drive']['folder']}")
        print(f"  • Credentials: {sanitized['google_drive']['credentials_file']}")
        print(f"  • Retention: {sanitized['google_drive']['retention_days']} days")
        
        print(f"\nSharing:")
        emails = sanitized['sharing']['emails']
        print(f"  • Emails: {', '.join(emails) if emails else 'None'}")
        print(f"  • Role: {sanitized['sharing']['role']}")
        print(f"  • Public: {'Yes' if sanitized['sharing']['make_public'] else 'No'}")
        
        if sanitized.get('database'):
            print(f"\nDatabase (from config):")
            print(f"  • Host: {sanitized['database']['host']}")
            print(f"  • Name: {sanitized['database']['name']}")
            print(f"  • User: {sanitized['database']['user']}")
        else:
            print(f"\nDatabase: Will extract from wp-config.php")
        
        print(f"\nEnvironment: {sanitized['environment']}")


# Instancia global del loader
_config_loader = SecureConfigLoader()


def load_config(config_file: Optional[str] = None) -> Config:
    """Load configuration securely"""
    return _config_loader.load_config(config_file)


def create_env_template() -> None:
    """Create secure environment template"""
    _config_loader.create_secure_env_template()


def print_config_summary(config: Config) -> None:
    """Print configuration summary safely"""
    _config_loader.print_config_summary(config)
