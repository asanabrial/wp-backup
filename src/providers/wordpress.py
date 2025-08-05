"""
Simplified WordPress backup provider
"""

import os
import re
import shutil
import subprocess
import tempfile
import tarfile
from pathlib import Path
from typing import Optional

from .base import BackupProvider
from ..core.config import WordPressConfig, DatabaseCredentials
from ..security.secrets import SecretManager
from ..utils import Logger, get_file_size


class WordPressProvider(BackupProvider):
    """Provider simplificado y seguro para WordPress"""
    
    def __init__(self, config: WordPressConfig):
        self.config = config
        self.secret_manager = SecretManager()
        self.logger = Logger()
        self._db_credentials: Optional[DatabaseCredentials] = None
    
    def authenticate(self) -> bool:
        """Autentica verificando acceso a WordPress y MySQL"""
        try:
            # Verificar acceso a directorio WordPress
            if not self.config.path.exists():
                self.logger.error(f"WordPress directory not found: {self.config.path}")
                return False
            
            # Verificar acceso a wp-config.php
            wp_config_path = self.config.path / "wp-config.php"
            if not wp_config_path.exists():
                self.logger.error(f"wp-config.php not found in {self.config.path}")
                return False
            
            # Extraer y validar credenciales de BD
            self._db_credentials = self._extract_db_credentials()
            if not self._db_credentials:
                return False
            
            # Probar conexión MySQL
            return self._test_mysql_connection()
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {self.secret_manager.mask_sensitive_data(str(e))}")
            return False
    
    def validate_setup(self) -> bool:
        """Valida que el setup esté correcto"""
        try:
            # Verificar herramientas MySQL
            if not self._check_mysql_tools():
                return False
            
            # Verificar permisos de directorio
            if not self._check_directory_permissions():
                return False
            
            self.logger.success("WordPress setup validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Setup validation failed: {e}")
            return False
    
    def create_backup(self, temp_dir: str) -> Optional[str]:
        """Crea backup completo de WordPress"""
        try:
            self.logger.progress("Creating WordPress backup...", "📦")
            
            # Crear subdirectorios
            files_dir = os.path.join(temp_dir, "files")
            db_file = os.path.join(temp_dir, "database.sql.gz")
            
            # 1. Backup de archivos
            if not self._backup_files(files_dir):
                return None
            
            # 2. Backup de base de datos
            if not self._backup_database(db_file, temp_dir):
                return None
            
            # 3. Crear archivo combinado
            combined_backup = self._create_combined_backup(temp_dir)
            
            if combined_backup:
                backup_size = get_file_size(combined_backup)
                self.logger.success(f"WordPress backup created: {backup_size}")
            
            return combined_backup
            
        except Exception as e:
            self.logger.error(f"Backup creation failed: {self.secret_manager.mask_sensitive_data(str(e))}")
            return None
    
    def _extract_db_credentials(self) -> Optional[DatabaseCredentials]:
        """Extrae credenciales de BD de wp-config.php de forma segura"""
        try:
            self.logger.info("Extracting database credentials...", "🔑")
            
            wp_config_path = self.config.path / "wp-config.php"
            
            with open(wp_config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Patrones para extraer credenciales
            patterns = {
                'name': r"define\s*\(\s*['\"]DB_NAME['\"],\s*['\"]([^'\"]+)['\"]",
                'user': r"define\s*\(\s*['\"]DB_USER['\"],\s*['\"]([^'\"]+)['\"]", 
                'password': r"define\s*\(\s*['\"]DB_PASSWORD['\"],\s*['\"]([^'\"]*)['\"]",
                'host': r"define\s*\(\s*['\"]DB_HOST['\"],\s*['\"]([^'\"]+)['\"]"
            }
            
            credentials_data = {}
            for key, pattern in patterns.items():
                match = re.search(pattern, content)
                if match:
                    credentials_data[key] = match.group(1)
                else:
                    self.logger.error(f"Could not extract {key} from wp-config.php")
                    return None
            
            credentials = DatabaseCredentials(**credentials_data)
            
            # Log de forma segura (sin password)
            self.logger.success("Database credentials extracted:")
            self.logger.info(f"   • Database: {credentials.name}")
            self.logger.info(f"   • User: {credentials.user}")
            self.logger.info(f"   • Host: {credentials.host}")
            
            return credentials
            
        except Exception as e:
            self.logger.error(f"Error extracting credentials: {e}")
            return None
    
    def _test_mysql_connection(self) -> bool:
        """Prueba conexión MySQL de forma segura"""
        if not self._db_credentials:
            return False
        
        try:
            # Comando de prueba sin exponer password en logs
            test_cmd = [
                'mysql',
                f'--host={self._db_credentials.host}',
                f'--user={self._db_credentials.user}',
                '--execute=SELECT VERSION();',
                self._db_credentials.name
            ]
            
            # Usar variable de entorno para password (más seguro)
            env = dict(os.environ, MYSQL_PWD=self._db_credentials.password)
            
            result = subprocess.run(
                test_cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=10
            )
            
            if result.returncode == 0:
                self.logger.success("MySQL connection test successful")
                return True
            else:
                # Enmascarar datos sensibles en el error
                masked_error = self.secret_manager.mask_sensitive_data(result.stderr)
                self.logger.error(f"MySQL connection failed: {masked_error}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("MySQL connection timeout")
            return False
        except Exception as e:
            self.logger.error(f"MySQL connection test failed: {e}")
            return False
    
    def _check_mysql_tools(self) -> bool:
        """Verifica disponibilidad de herramientas MySQL"""
        tools = ['mysql', 'mysqldump']
        
        for tool in tools:
            try:
                result = subprocess.run(['which', tool], capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.success(f"✅ {tool} found at: {result.stdout.strip()}")
                else:
                    self.logger.error(f"❌ {tool} not found")
                    self._show_mysql_installation_help()
                    return False
            except Exception:
                self.logger.error(f"❌ Error checking {tool}")
                return False
        
        return True
    
    def _show_mysql_installation_help(self):
        """Muestra ayuda para instalar MySQL tools"""
        self.logger.info("💡 MySQL tools installation:")
        self.logger.info("   • Ubuntu/Debian: sudo apt-get install mysql-client")
        self.logger.info("   • CentOS/RHEL: sudo yum install mysql")
        self.logger.info("   • macOS: brew install mysql-client")
    
    def _check_directory_permissions(self) -> bool:
        """Verifica permisos de directorio"""
        try:
            # Verificar lectura de WordPress
            if not os.access(self.config.path, os.R_OK):
                self.logger.error(f"No read permission for WordPress directory: {self.config.path}")
                return False
            
            # Verificar escritura en directorio de backup
            backup_parent = self.config.backup_dir.parent
            if not os.access(backup_parent, os.W_OK):
                self.logger.error(f"No write permission for backup directory: {backup_parent}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Permission check failed: {e}")
            return False
    
    def _backup_files(self, files_dir: str) -> bool:
        """Crea backup de archivos WordPress"""
        try:
            self.logger.progress("Backing up WordPress files...", "📁")
            
            # Copiar archivos WordPress
            shutil.copytree(str(self.config.path), files_dir, 
                          ignore=shutil.ignore_patterns('*.log', '.git', '__pycache__'))
            
            self.logger.success("WordPress files backup completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Files backup failed: {e}")
            return False
    
    def _backup_database(self, db_file: str, temp_dir: str = None) -> bool:
        """Crea backup de base de datos"""
        try:
            self.logger.progress("Backing up database...", "💾")
            
            if not self._db_credentials:
                self.logger.error("No database credentials available")
                return False

            # Comando mysqldump con directorio temporal alternativo
            # MySQL usa la variable de entorno TMPDIR, no el parámetro --tmpdir
            tmpdir = temp_dir if temp_dir else '/tmp'
            
            mysqldump_cmd = [
                'mysqldump',
                f'--host={self._db_credentials.host}',
                f'--user={self._db_credentials.user}',
                '--single-transaction',
                '--routines', 
                '--triggers',
                '--lock-tables=false',  # Evitar problemas con permisos
                self._db_credentials.name
            ]
            
            # Usar variable de entorno para password Y para tmpdir
            env = dict(os.environ, 
                      MYSQL_PWD=self._db_credentials.password,
                      TMPDIR=tmpdir)  # MySQL usa TMPDIR en lugar de --tmpdir
            
            # Ejecutar mysqldump con compresión
            with open(db_file, 'wb') as f:
                mysqldump_process = subprocess.Popen(
                    mysqldump_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env
                )
                
                gzip_process = subprocess.Popen(
                    ['gzip'],
                    stdin=mysqldump_process.stdout,
                    stdout=f,
                    stderr=subprocess.PIPE
                )
                
                mysqldump_process.stdout.close()
                gzip_stdout, gzip_stderr = gzip_process.communicate()
                mysqldump_stdout, mysqldump_stderr = mysqldump_process.communicate()
                
                if mysqldump_process.returncode != 0:
                    masked_error = self.secret_manager.mask_sensitive_data(
                        mysqldump_stderr.decode() if mysqldump_stderr else "Unknown error"
                    )
                    raise Exception(f"mysqldump failed: {masked_error}")
                
                if gzip_process.returncode != 0:
                    raise Exception(f"gzip failed: {gzip_stderr.decode() if gzip_stderr else 'Unknown error'}")
            
            # Verificar que el archivo se creó correctamente
            if not os.path.exists(db_file) or os.path.getsize(db_file) == 0:
                raise Exception("Database backup file is empty or not created")
            
            db_size = get_file_size(db_file)
            self.logger.success(f"Database backup completed: {db_size}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Database backup failed: {e}")
            return False
    
    def _create_combined_backup(self, temp_dir: str) -> Optional[str]:
        """Crea archivo combinado tar.gz"""
        try:
            self.logger.progress("Creating combined backup archive...", "🗜️")
            
            # Asegurar que el directorio de backup existe
            os.makedirs(self.config.backup_dir, exist_ok=True)
            
            # Nombre del archivo final
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{self.config.domain}_{timestamp}.tar.gz"
            backup_file = self.config.backup_dir / backup_filename
            
            # Crear archivo tar.gz
            with tarfile.open(str(backup_file), "w:gz") as tar:
                for item in os.listdir(temp_dir):
                    item_path = os.path.join(temp_dir, item)
                    tar.add(item_path, arcname=item)
            
            return str(backup_file)
            
        except Exception as e:
            self.logger.error(f"Combined backup creation failed: {e}")
            return None
