"""
Simplified Command Line Interface for WordPress Backup Tool v3.0
"""

import sys
import click
from pathlib import Path
from typing import Optional

from .core.config import load_config, print_config_summary, create_env_template
from .core.backup import BackupOrchestrator
from .providers.wordpress import WordPressProvider
from .providers.gdrive import GoogleDriveProvider
from .security.secrets import SecretManager
from .utils import Logger


@click.group()
def cli():
    """WordPress Backup Tool v3.0 - Secure and Simplified"""
    pass


@cli.command()
@click.option('--dry-run', is_flag=True, help='Show configuration without executing')
@click.option('--config-file', help='Custom configuration file path')
def backup(dry_run: bool, config_file: Optional[str]):
    """Execute WordPress backup"""
    
    logger = Logger()
    
    try:
        # Cargar configuración de forma segura
        config = load_config(config_file)
        
        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made", "🔍")
            print_config_summary(config)
            return
        
        # Crear providers
        wp_provider = WordPressProvider(config.wordpress)
        storage_provider = GoogleDriveProvider(config.google_drive)
        
        # Ejecutar backup
        orchestrator = BackupOrchestrator(wp_provider, storage_provider, config)
        result = orchestrator.execute_backup()
        
        # Mostrar resumen
        orchestrator.print_summary(result)
        
        sys.exit(0 if result.success else 1)
        
    except KeyboardInterrupt:
        logger.warning("Backup cancelled by user", "⚠️")
        sys.exit(1)
    except Exception as e:
        # Enmascarar datos sensibles en errores
        secret_manager = SecretManager()
        masked_error = secret_manager.mask_sensitive_data(str(e))
        logger.error(f"Fatal error: {masked_error}")
        sys.exit(1)


@cli.command()
def init():
    """Initialize secure configuration"""
    
    logger = Logger()
    
    try:
        # Verificar si ya existe configuración
        env_file = Path('.env')
        env_local_file = Path('.env.local')
        
        if env_local_file.exists():
            response = input(".env.local already exists. Overwrite? [y/N]: ")
            if response.lower() != 'y':
                logger.info("Configuration not modified")
                return
        
        # Crear template seguro
        create_env_template()
        
        logger.success("Secure configuration template created")
        logger.info("Next steps:")
        logger.info("1. Copy .env.local.example to .env.local")
        logger.info("2. Fill in your configuration values")
        logger.info("3. Set up Google Drive OAuth credentials")
        logger.info("4. Run: wp-backup backup --dry-run")
        
    except Exception as e:
        logger.error(f"Initialization failed: {e}")


@cli.command()
@click.option('--test-wordpress', is_flag=True, help='Test WordPress connection only')
@click.option('--test-gdrive', is_flag=True, help='Test Google Drive connection only')
def test(test_wordpress: bool, test_gdrive: bool):
    """Test connections and configuration"""
    
    logger = Logger()
    
    try:
        config = load_config()
        
        # Probar WordPress si se solicita o por defecto
        if test_wordpress or not any([test_wordpress, test_gdrive]):
            logger.info("Testing WordPress connection...", "🔍")
            wp_provider = WordPressProvider(config.wordpress)
            
            if wp_provider.validate_setup() and wp_provider.authenticate():
                logger.success("✅ WordPress connection test passed")
            else:
                logger.error("❌ WordPress connection test failed")
                return
        
        # Probar Google Drive si se solicita o por defecto
        if test_gdrive or not any([test_wordpress, test_gdrive]):
            logger.info("Testing Google Drive connection...", "🔍")
            storage_provider = GoogleDriveProvider(config.google_drive)
            
            if storage_provider.authenticate():
                logger.success("✅ Google Drive connection test passed")
            else:
                logger.error("❌ Google Drive connection test failed")
                return
        
        logger.success("🎉 All connection tests passed!")
        
    except Exception as e:
        secret_manager = SecretManager()
        masked_error = secret_manager.mask_sensitive_data(str(e))
        logger.error(f"Connection test failed: {masked_error}")


@cli.command()
def security_scan():
    """Scan for potential security issues"""
    
    logger = Logger()
    secret_manager = SecretManager()
    
    try:
        logger.info("Scanning for security issues...", "🔍")
        
        # Verificar archivos de código por secretos hardcodeados
        code_files = [
            'wp_backup/core/config.py',
            'wp_backup/providers/wordpress.py',
            'wp_backup/providers/gdrive.py',
            'wp_backup/cli.py',
        ]
        
        issues = secret_manager.verify_no_hardcoded_secrets(code_files)
        
        if issues:
            logger.warning("Security issues found:")
            for issue in issues:
                logger.warning(f"  • {issue}")
        else:
            logger.success("✅ No hardcoded secrets found in code")
        
        # Verificar seguridad del entorno
        from .security.validator import ConfigValidator
        validator = ConfigValidator()
        env_issues = validator.validate_environment_security()
        
        if env_issues:
            logger.warning("Environment security issues:")
            for issue in env_issues:
                logger.warning(f"  • {issue}")
        else:
            logger.success("✅ Environment security looks good")
        
        if not issues and not env_issues:
            logger.success("🎉 Security scan passed!")
        
    except Exception as e:
        logger.error(f"Security scan failed: {e}")


# Función principal para compatibilidad con versión anterior
def main():
    """Main entry point for backwards compatibility"""
    cli()


if __name__ == '__main__':
    cli()
