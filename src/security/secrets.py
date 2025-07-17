"""
Secure secret management for WordPress Backup Tool
"""

import os
import re
from pathlib import Path
from typing import Optional, Dict, Any
from getpass import getpass


class SecretManager:
    """Manejo seguro de secretos con múltiples fuentes"""
    
    def __init__(self):
        self.env_file_paths = [
            '.env.local',  # Prioridad más alta (no versionado)
            '.env',        # Archivo estándar
        ]
        self._secrets_cache: Dict[str, str] = {}
    
    def get_secret(self, key: str, prompt_message: Optional[str] = None) -> Optional[str]:
        """
        Obtiene un secreto de múltiples fuentes en orden de prioridad:
        1. Variables de entorno del sistema
        2. Archivo .env.local (no versionado)
        3. Archivo .env
        4. Prompt interactivo (solo si se proporciona mensaje)
        """
        # 1. Variables de entorno del sistema
        value = os.getenv(key)
        if value:
            return value
        
        # 2. Archivos .env en orden de prioridad
        for env_file in self.env_file_paths:
            value = self._load_from_env_file(key, env_file)
            if value:
                return value
        
        # 3. Prompt interactivo como último recurso
        if prompt_message:
            return self._prompt_for_secret(key, prompt_message)
        
        return None
    
    def _load_from_env_file(self, key: str, env_file: str) -> Optional[str]:
        """Carga valor desde archivo .env específico"""
        env_path = Path(env_file)
        if not env_path.exists():
            return None
        
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or '=' not in line:
                        continue
                    
                    env_key, env_value = line.split('=', 1)
                    if env_key.strip() == key:
                        # Remover comillas si existen
                        value = env_value.strip().strip('\'"')
                        return value if value else None
        except Exception:
            pass
        
        return None
    
    def _prompt_for_secret(self, key: str, message: str) -> Optional[str]:
        """Solicita secreto de forma interactiva"""
        try:
            if 'password' in key.lower() or 'secret' in key.lower():
                value = getpass(f"{message}: ")
            else:
                value = input(f"{message}: ").strip()
            
            return value if value else None
        except KeyboardInterrupt:
            return None
    
    def mask_sensitive_data(self, text: str) -> str:
        """
        Enmascara datos sensibles en texto para logging seguro
        """
        if not text:
            return text
        
        # Patrones de datos sensibles
        patterns = [
            # Passwords
            (r'(password["\']?\s*[:=]\s*["\']?)([^"\'\s]+)(["\']?)', r'\1***\3'),
            # API Keys
            (r'((?:api[_-]?key|access[_-]?token)["\']?\s*[:=]\s*["\']?)([^"\'\s]+)(["\']?)', r'\1***\3'),
            # URLs con credenciales
            (r'(https?://[^:]+:)([^@]+)(@)', r'\1***\3'),
            # Emails (parcial)
            (r'(\w+)(@\w+\.\w+)', r'***\2'),
            # Paths con información sensible
            (r'(/[^/]*(?:secret|private|key|credential)[^/]*/)([^/\s]+)', r'\1***'),
        ]
        
        masked_text = text
        for pattern, replacement in patterns:
            masked_text = re.sub(pattern, replacement, masked_text, flags=re.IGNORECASE)
        
        return masked_text
    
    def validate_secret_strength(self, secret: str, min_length: int = 8) -> bool:
        """Valida la fortaleza de un secreto"""
        if not secret or len(secret) < min_length:
            return False
        
        # Para passwords, verificar complejidad básica
        if 'password' in secret.lower():
            has_upper = any(c.isupper() for c in secret)
            has_lower = any(c.islower() for c in secret)
            has_digit = any(c.isdigit() for c in secret)
            return has_upper and has_lower and has_digit
        
        return True
    
    def create_env_template(self, config_keys: Dict[str, str], output_file: str = '.env.local.example') -> None:
        """Crea un archivo template para configuración"""
        template_content = [
            "# Local configuration file - DO NOT COMMIT TO VERSION CONTROL",
            "# Copy this file to .env.local and fill in your values",
            "",
        ]
        
        for key, description in config_keys.items():
            template_content.append(f"# {description}")
            template_content.append(f"{key}=")
            template_content.append("")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(template_content))
    
    def verify_no_hardcoded_secrets(self, file_paths: list[str]) -> list[str]:
        """
        Verifica que no haya secretos hardcodeados en archivos de código
        Retorna lista de problemas encontrados
        """
        issues = []
        
        # Patrones que indican posibles secretos hardcodeados
        suspicious_patterns = [
            r'password\s*=\s*["\'][^"\']{3,}["\']',
            r'secret\s*=\s*["\'][^"\']{10,}["\']',
            r'api[_-]?key\s*=\s*["\'][^"\']{10,}["\']',
            r'token\s*=\s*["\'][^"\']{10,}["\']',
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # emails reales (no en decoradores)
        ]
        
        # Patrones a ignorar (falsos positivos)
        ignore_patterns = [
            r'@click\.',  # Decoradores de Click
            r'@cli\.',    # Decoradores CLI
            r'help=',     # Texto de ayuda
            r'description=',  # Descripciones
            r'example\.com',  # Emails de ejemplo
            r'your-.*\.com',  # Placeholders
        ]
        
        for file_path in file_paths:
            if not Path(file_path).exists():
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                for i, line in enumerate(content.split('\n'), 1):
                    # Saltar comentarios y documentación
                    if line.strip().startswith('#') or line.strip().startswith('"""'):
                        continue
                    
                    # Verificar patrones de ignorar primero
                    should_ignore = any(re.search(ignore_pattern, line, re.IGNORECASE) 
                                      for ignore_pattern in ignore_patterns)
                    if should_ignore:
                        continue
                    
                    for pattern in suspicious_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            issues.append(f"{file_path}:{i} - Possible hardcoded secret: {line.strip()[:50]}...")
                            
            except Exception as e:
                issues.append(f"Error reading {file_path}: {e}")
        
        return issues
