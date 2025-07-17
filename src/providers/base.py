"""
Provider interfaces and base classes
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


@dataclass
class BackupResult:
    """Resultado de operación de backup"""
    success: bool = False
    backup_id: Optional[str] = None
    error: Optional[str] = None
    files_cleaned: int = 0
    duration: Optional[float] = None
    backup_size: Optional[str] = None


class BackupProvider(ABC):
    """Interfaz base para providers de backup"""
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Autentica con el servicio de backup"""
        pass
    
    @abstractmethod
    def create_backup(self, temp_dir: str) -> Optional[str]:
        """Crea backup y retorna la ruta del archivo"""
        pass
    
    @abstractmethod
    def validate_setup(self) -> bool:
        """Valida que el setup esté correcto"""
        pass


class StorageProvider(ABC):
    """Interfaz base para providers de almacenamiento"""
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Autentica con el servicio de almacenamiento"""
        pass
    
    @abstractmethod
    def upload(self, file_path: str) -> Optional[str]:
        """Sube archivo y retorna ID del archivo"""
        pass
    
    @abstractmethod
    def configure_access(self, permissions: Dict[str, Any]) -> bool:
        """Configura permisos de acceso"""
        pass
    
    @abstractmethod
    def cleanup_old_files(self, retention_days: int) -> int:
        """Limpia archivos antiguos y retorna cantidad eliminada"""
        pass
