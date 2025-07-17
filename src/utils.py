"""
Utilities for logging and common operations
"""

import os
from typing import Optional


class Logger:
    """Simple logger with emoji support"""
    
    @staticmethod
    def info(message: str, emoji: str = "💡") -> None:
        """Print info message with emoji"""
        print(f"{emoji} {message}")
    
    @staticmethod
    def success(message: str, emoji: str = "✅") -> None:
        """Print success message"""
        print(f"{emoji} {message}")
    
    @staticmethod
    def error(message: str, emoji: str = "❌") -> None:
        """Print error message"""
        print(f"{emoji} {message}")
    
    @staticmethod
    def warning(message: str, emoji: str = "⚠️") -> None:
        """Print warning message"""
        print(f"{emoji} {message}")
    
    @staticmethod
    def progress(message: str, emoji: str = "🔄") -> None:
        """Print progress message"""
        print(f"{emoji} {message}")


def get_file_size(file_path: str) -> str:
    """Get human readable file size"""
    size = os.path.getsize(file_path)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"


def ensure_directory(path: str) -> None:
    """Ensure directory exists, create if it doesn't"""
    os.makedirs(path, exist_ok=True)
