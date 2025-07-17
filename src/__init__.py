"""
WordPress Backup Tool v3.0 - Secure and Simplified
"""

__version__ = "3.0.0"
__author__ = "WordPress Backup Tool"
__description__ = "Secure WordPress Backup Tool with Google Drive Integration"

from .core import Config, load_config, BackupOrchestrator, BackupResult
from .providers import WordPressProvider, GoogleDriveProvider
from .security import SecretManager, ConfigValidator

__all__ = [
    'Config',
    'load_config', 
    'BackupOrchestrator',
    'BackupResult',
    'WordPressProvider',
    'GoogleDriveProvider', 
    'SecretManager',
    'ConfigValidator'
]
