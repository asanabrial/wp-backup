"""
Simplified backup orchestrator with better error handling
"""

import glob
import os
import shutil
import time
from datetime import datetime
from tempfile import TemporaryDirectory
from typing import Optional

from .config import Config
from ..providers.base import BackupProvider, StorageProvider, BackupResult
from ..security.secrets import SecretManager
from ..utils import Logger, get_file_size


class BackupOrchestrator:
    """Orquestador principal simplificado con manejo robusto de errores"""
    
    def __init__(self, 
                 backup_provider: BackupProvider,
                 storage_provider: StorageProvider,
                 config: Config):
        self.backup_provider = backup_provider
        self.storage_provider = storage_provider
        self.config = config
        self.secret_manager = SecretManager()
        self.logger = Logger()
    
    def execute_backup(self) -> BackupResult:
        """Ejecuta backup completo con manejo robusto de errores"""
        
        start_time = time.time()
        result = BackupResult()
        
        try:
            self.logger.progress("Starting WordPress backup...", "🚀")
            self.logger.info(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "📅")
            
            # 0. Limpiar directorios temporales huérfanos del inicio
            self._cleanup_temp_directories()
            
            # 1. Validar configuración
            if not self._validate_setup():
                result.error = "Setup validation failed"
                return result
            
            # 2. Autenticar providers
            if not self._authenticate_providers():
                result.error = "Provider authentication failed"
                return result
            
            # 3. Crear backup
            temp_dir_path = None
            try:
                with TemporaryDirectory(prefix='wp_backup_') as temp_dir:
                    temp_dir_path = temp_dir  # Guardar referencia para limpieza de emergencia
                    self.logger.info(f"Working directory: {temp_dir}", "📁")
                    
                    backup_file = self.backup_provider.create_backup(temp_dir)
                    if not backup_file:
                        result.error = "Backup creation failed"
                        return result
                    
                    # 4. Upload a almacenamiento
                    file_id = self.storage_provider.upload(backup_file)
                    if not file_id:
                        result.error = "Upload failed"
                        return result
                    
                    # 5. Configurar permisos
                    self.storage_provider.configure_access(self.config.sharing)
                    
                    # 6. Limpieza de archivos antiguos
                    cleaned = self.storage_provider.cleanup_old_files(self.config.google_drive.retention_days)
                    
                    # 7. Preparar resultado exitoso
                    result.success = True
                    result.backup_id = file_id
                    result.files_cleaned = cleaned
                    result.duration = time.time() - start_time
                    result.backup_size = get_file_size(backup_file)
                    
                    # Marcar temp_dir_path como None ya que se limpió correctamente
                    temp_dir_path = None
                    
            except Exception as temp_exception:
                # Si hay un error y el directorio temporal no se limpió, intentar limpieza manual
                if temp_dir_path and os.path.exists(temp_dir_path):
                    try:
                        shutil.rmtree(temp_dir_path)
                        self.logger.info(f"Emergency cleanup of temp directory: {os.path.basename(temp_dir_path)}")
                    except Exception as cleanup_ex:
                        self.logger.warning(f"Could not cleanup temp directory {temp_dir_path}: {cleanup_ex}")
                raise temp_exception
        
        except Exception as e:
            result.error = self.secret_manager.mask_sensitive_data(str(e))
            self.logger.error(f"Backup failed: {result.error}")
        
        finally:
            # Limpiar archivos locales
            self._cleanup_local_files()
        
        return result
    
    def _validate_setup(self) -> bool:
        """Valida configuración y setup"""
        try:
            self.logger.progress("Validating setup...", "🔍")
            
            # Imprimir configuración de forma segura
            self._print_configuration()
            
            # Validar backup provider
            if not self.backup_provider.validate_setup():
                return False
            
            self.logger.success("Setup validation completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Setup validation failed: {e}")
            return False
    
    def _authenticate_providers(self) -> bool:
        """Autentica todos los providers"""
        try:
            self.logger.progress("Authenticating providers...", "🔐")
            
            # Autenticar backup provider
            if not self.backup_provider.authenticate():
                self.logger.error("Backup provider authentication failed")
                return False
            
            # Autenticar storage provider
            if not self.storage_provider.authenticate():
                self.logger.error("Storage provider authentication failed")
                return False
            
            self.logger.success("All providers authenticated successfully")
            return True
            
        except Exception as e:
            masked_error = self.secret_manager.mask_sensitive_data(str(e))
            self.logger.error(f"Provider authentication failed: {masked_error}")
            return False
    
    def _print_configuration(self) -> None:
        """Imprime configuración de forma segura"""
        self.logger.info("Current configuration:", "💡")
        self.logger.info(f"   • Domain: {self.config.wordpress.domain}")
        self.logger.info(f"   • Drive folder: {self.config.google_drive.folder}")
        self.logger.info(f"   • Retention: {self.config.google_drive.retention_days} days")
        self.logger.info(f"   • Environment: {self.config.environment}")
        
        # Información de compartir (enmascarada)
        if self.config.sharing.emails:
            masked_emails = [self.secret_manager.mask_sensitive_data(email) 
                           for email in self.config.sharing.emails]
            self.logger.info(f"   • Share with: {', '.join(masked_emails)}")
        
        self.logger.info("   • Local storage: None (temporary only)")
    
    def _cleanup_local_files(self) -> None:
        """Limpia archivos locales y directorios temporales huérfanos"""
        try:
            self.logger.progress("Cleaning up local files...", "🧹")
            
            # 1. Limpiar directorio de backup si está vacío
            if self.config.wordpress.backup_dir.exists():
                try:
                    # Solo eliminar si está vacío
                    if not any(self.config.wordpress.backup_dir.iterdir()):
                        self.config.wordpress.backup_dir.rmdir()
                        self.logger.info("Removed empty backup directory")
                except OSError:
                    pass  # Directorio no está vacío, está bien
            
            # 2. Limpiar directorios temporales huérfanos de wp_backup_*
            self._cleanup_temp_directories()
            
            self.logger.success("Local cleanup completed")
            
        except Exception as e:
            self.logger.warning(f"Local cleanup warning: {e}")
    
    def _cleanup_temp_directories(self) -> None:
        """Limpia directorios temporales huérfanos de wp_backup_*"""
        try:
            # Buscar directorios temporales huérfanos en /tmp
            temp_dirs = glob.glob('/tmp/wp_backup_*')
            
            if temp_dirs:
                self.logger.info(f"Found {len(temp_dirs)} temporary directories to clean")
                
                for temp_dir in temp_dirs:
                    try:
                        if os.path.isdir(temp_dir):
                            shutil.rmtree(temp_dir)
                            self.logger.info(f"Removed temporary directory: {os.path.basename(temp_dir)}")
                    except Exception as e:
                        self.logger.warning(f"Could not remove {temp_dir}: {e}")
                
                self.logger.success(f"Cleaned {len(temp_dirs)} temporary directories")
            else:
                self.logger.info("No temporary directories found to clean")
                
        except Exception as e:
            self.logger.warning(f"Temporary directory cleanup failed: {e}")
    
    def print_summary(self, result: BackupResult) -> None:
        """Imprime resumen final"""
        print()
        
        if result.success:
            self.logger.success("🎉 Backup completed successfully!")
            
            print()
            self.logger.info(f"📊 BACKUP SUMMARY", "📊")
            self.logger.info(f"   • Status: ✅ Success")
            self.logger.info(f"   • Backup ID: {result.backup_id}")
            if result.backup_size:
                self.logger.info(f"   • Size: {result.backup_size}")
            if result.duration:
                self.logger.info(f"   • Duration: {result.duration:.1f} seconds")
            self.logger.info(f"   • Files cleaned: {result.files_cleaned}")
            
            print()
            self.logger.success("☁️ Google Drive: ✅ Backup uploaded successfully")
            self.logger.success("🧹 Local files: ✅ Cleaned up (no space used)")
            
        else:
            self.logger.error("❌ Backup failed!")
            
            print()
            self.logger.info(f"📊 BACKUP SUMMARY", "📊")
            self.logger.info(f"   • Status: ❌ Failed")
            self.logger.info(f"   • Error: {result.error}")
            if result.duration:
                self.logger.info(f"   • Duration: {result.duration:.1f} seconds")
            
            print()
            self.logger.warning("⚠️ Please check the error message above and configuration")
    
    def test_connections(self) -> bool:
        """Prueba conexiones sin ejecutar backup"""
        try:
            self.logger.info("Testing connections...", "🔍")
            
            # Probar configuración
            if not self._validate_setup():
                return False
            
            # Probar autenticación
            if not self._authenticate_providers():
                return False
            
            self.logger.success("✅ All connection tests passed!")
            return True
            
        except Exception as e:
            masked_error = self.secret_manager.mask_sensitive_data(str(e))
            self.logger.error(f"Connection test failed: {masked_error}")
            return False
