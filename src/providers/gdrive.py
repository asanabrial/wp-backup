"""
Simplified and secure Google Drive provider
"""

import os
import pickle
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from .base import StorageProvider
from ..core.config import GoogleDriveConfig, SharingConfig
from ..security.secrets import SecretManager
from ..utils import Logger


class GoogleDriveProvider(StorageProvider):
    """Provider simplificado y seguro para Google Drive con OAuth 2.0"""
    
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    TOKEN_FILE = 'token.pickle'
    
    def __init__(self, config: GoogleDriveConfig):
        self.config = config
        self.secret_manager = SecretManager()
        self.logger = Logger()
        self.service = None
        self.folder_id = None
    
    def authenticate(self) -> bool:
        """Autentica con Google Drive usando OAuth 2.0 de forma segura con refresh automático"""
        try:
            creds = self._load_existing_credentials()
            
            # Validar y refrescar credenciales si es necesario
            if not self._validate_and_refresh_credentials(creds):
                # Si no se pueden refrescar, ejecutar flujo OAuth completo
                if not self._run_oauth_flow():
                    return False
                
                # Recargar credenciales después del flujo OAuth
                creds = self._load_existing_credentials()
                if not creds:
                    self.logger.error("OAuth flow completed but no valid credentials available")
                    return False
            
            # Crear servicio de Google Drive
            self.service = build('drive', 'v3', credentials=creds)
            
            # Probar conexión
            if self._test_connection():
                self.logger.success("Google Drive authentication successful")
                return True
            else:
                return False
                
        except Exception as e:
            masked_error = self.secret_manager.mask_sensitive_data(str(e))
            self.logger.error(f"Google Drive authentication failed: {masked_error}")
            return False
    
    def _load_existing_credentials(self) -> Optional[Credentials]:
        """Carga credenciales existentes desde el archivo token"""
        if not os.path.exists(self.TOKEN_FILE):
            return None
            
        try:
            with open(self.TOKEN_FILE, 'rb') as token:
                creds = pickle.load(token)
                return creds
        except Exception as e:
            self.logger.warning(f"Error loading existing token: {e}")
            return None
    
    def _validate_and_refresh_credentials(self, creds: Optional[Credentials]) -> bool:
        """Valida credenciales y las refresca automáticamente si es necesario"""
        if not creds:
            self.logger.info("No existing credentials found")
            return False
        
        # Si la renovación automática está deshabilitada, solo verificar validez
        if not self.config.auto_refresh:
            if creds.valid:
                self.logger.info("Existing credentials are valid (auto-refresh disabled)")
                return True
            else:
                self.logger.info("Credentials invalid and auto-refresh disabled - need new authorization")
                return False
        
        # Forzar refresh si está configurado
        if self.config.force_refresh_on_start and creds.refresh_token:
            self.logger.info("🔄 Force refresh on start enabled")
            return self._refresh_access_token(creds)
        
        # Si las credenciales son válidas, verificar si necesitan renovación preventiva
        if creds.valid:
            if creds.expiry:
                time_to_expiry = (creds.expiry - datetime.now()).total_seconds() / 60  # en minutos
                if time_to_expiry < self.config.refresh_threshold_minutes and creds.refresh_token:
                    self.logger.info(f"🔄 Token expires in {time_to_expiry:.1f} minutes - refreshing preventively")
                    return self._refresh_access_token(creds)
            
            self.logger.info("Existing credentials are valid")
            return True
        
        # Si están expiradas pero tenemos refresh_token, intentar refrescar
        if creds.expired and creds.refresh_token:
            return self._refresh_access_token(creds)
        
        # Si no hay refresh_token o no están simplemente expiradas
        self.logger.info("Credentials cannot be refreshed - need new authorization")
        return False
    
    def _refresh_access_token(self, creds: Credentials) -> bool:
        """Refresca el access token usando el refresh token"""
        try:
            self.logger.info("🔄 Refreshing access token...")
            
            # Intentar refrescar el token
            creds.refresh(Request())
            
            # Guardar las credenciales actualizadas
            self._save_credentials(creds)
            
            # Verificar que el token funciona
            if creds.valid:
                self.logger.success("✅ Access token refreshed successfully")
                self.logger.info(f"   🕒 Token expires: {creds.expiry.strftime('%Y-%m-%d %H:%M:%S UTC') if creds.expiry else 'Unknown'}")
                return True
            else:
                self.logger.warning("⚠️ Token refresh completed but credentials still not valid")
                return False
                
        except Exception as e:
            error_msg = str(e).lower()
            
            if "invalid_grant" in error_msg or "token_expired" in error_msg:
                self.logger.warning("🔄 Refresh token has expired - new authorization required")
                self.logger.info("   💡 This is normal after long periods of inactivity")
            elif "invalid_client" in error_msg:
                self.logger.warning("❌ OAuth client configuration issue")
                self.logger.info("   💡 Check your Google Cloud Console OAuth settings")
            else:
                self.logger.warning(f"⚠️ Error refreshing token: {e}")
            
            return False
    
    def _save_credentials(self, creds: Credentials) -> bool:
        """Guarda credenciales al archivo token de forma segura"""
        try:
            # Crear backup del token anterior si existe
            if os.path.exists(self.TOKEN_FILE):
                backup_file = f"{self.TOKEN_FILE}.backup"
                try:
                    os.rename(self.TOKEN_FILE, backup_file)
                except Exception:
                    pass  # Si no se puede hacer backup, continuar
            
            # Guardar nuevas credenciales
            with open(self.TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
            
            self.logger.info("💾 Credentials saved successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving credentials: {e}")
            return False
    
    def _ensure_valid_credentials(self) -> bool:
        """Asegura que las credenciales estén válidas antes de operaciones críticas"""
        if not self.service:
            return False
        
        # Si la renovación automática está deshabilitada, solo verificar validez básica
        if not self.config.auto_refresh:
            try:
                # Hacer una llamada simple para verificar que funcionan
                self.service.about().get(fields="user").execute()
                return True
            except Exception as e:
                self.logger.warning(f"Credentials validation failed: {e}")
                return False
        
        try:
            # Obtener credenciales del servicio
            creds = self.service._http.credentials if hasattr(self.service, '_http') else None
            
            if not creds:
                self.logger.warning("No credentials available in service")
                return False
            
            # Si el token expira en menos del umbral configurado, refrescarlo preventivamente
            if creds.expiry and creds.expired:
                self.logger.info("🔄 Token expired, refreshing before operation...")
                return self._refresh_access_token(creds)
            elif creds.expiry:
                time_to_expiry = (creds.expiry - datetime.now()).total_seconds() / 60  # en minutos
                if time_to_expiry < self.config.refresh_threshold_minutes:
                    self.logger.info(f"🔄 Token expires in {time_to_expiry:.1f} minutes, refreshing preventively...")
                    return self._refresh_access_token(creds)
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Error validating credentials: {e}")
            return False
    
    def _run_oauth_flow(self) -> bool:
        """Ejecuta flujo OAuth 2.0 de forma segura con refresh tokens"""
        try:
            if not self.config.credentials_file.exists():
                self.logger.error(f"Credentials file not found: {self.config.credentials_file}")
                self._show_oauth_setup_help()
                return False
            
            self.logger.info("Starting OAuth 2.0 flow...")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.config.credentials_file), self.SCOPES
            )
            
            # Configurar para obtener refresh tokens
            flow.authorization_url_options = {'access_type': 'offline', 'prompt': 'consent'}
            
            # Ejecutar flujo OAuth 2.0
            # Detectar si estamos en VPS/servidor (sin DISPLAY)
            is_server = not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY')
            
            if is_server:
                self.logger.info("🖥️ Server environment detected - using manual authorization")
                creds = self._manual_oauth_flow(flow)
            else:
                try:
                    # Intentar con servidor local en entornos de escritorio
                    self.logger.info("Attempting OAuth with local server...")
                    creds = flow.run_local_server(port=0)
                except Exception as local_error:
                    # Fallback a método manual
                    error_msg = str(local_error).lower()
                    if any(x in error_msg for x in ["connection", "port", "localhost", "timeout", "refused", "server"]):
                        self.logger.info("⚠️ Local server not accessible - switching to manual flow")
                    else:
                        self.logger.warning(f"Local server OAuth failed: {local_error}")
                    
                    self.logger.info("🔄 Switching to manual authorization flow...")
                    creds = self._manual_oauth_flow(flow)
            
            # Verificar que obtenemos refresh token
            if not creds.refresh_token:
                self.logger.warning("⚠️ No refresh token received")
                self.logger.info("   💡 This might happen if you've already authorized this app")
                self.logger.info("   💡 To force refresh token, revoke access in Google Account settings")
                self.logger.info("   💡 Go to: https://myaccount.google.com/permissions")
                # Continuar de todos modos, el token de acceso actual funcionará
            else:
                self.logger.success("✅ Refresh token obtained - automatic renewal enabled")
            
            # Guardar token para uso futuro
            if not self._save_credentials(creds):
                self.logger.error("Failed to save credentials")
                return False
            
            self.logger.success("OAuth 2.0 flow completed successfully")
            self.logger.info("Token saved for future use")
            
            return True
            
        except Exception as e:
            self.logger.error(f"OAuth flow failed: {e}")
            return False
    
    def _manual_oauth_flow(self, flow):
        """Ejecuta flujo OAuth manual para VPS/servidores con refresh tokens"""
        # Para servidores sin navegador - configurar redirect_uri apropiado
        flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
        
        # Generar URL con parámetros para refresh tokens
        auth_url, _ = flow.authorization_url(
            prompt='consent',
            access_type='offline'
        )
        
        print("\n" + "="*60)
        print("🔐 GOOGLE DRIVE AUTHORIZATION REQUIRED")
        print("="*60)
        print("⚠️ VPS/Remote server detected - using manual authorization")
        print("🔄 Requesting refresh token for automatic renewal")
        print()
        print("📱 On your computer/phone:")
        print(f"   1. Open: {auth_url}")
        print("   2. Sign in with Google")
        print("   3. Click 'Allow' (accept all permissions)")
        print()
        print("💻 After authorization, you'll see:")
        print("   ┌─────────────────────────────────────┐")
        print("   │ Please copy this code, switch to    │")
        print("   │ your application and paste it there:│")
        print("   │                                     │")
        print("   │ 4/0AX4XfWi_example_code_here...     │")
        print("   └─────────────────────────────────────┘")
        print()
        print("🔐 Copy the ENTIRE code (starts with 4/0A...)")
        print("💡 Tip: Use Ctrl+A to select all, then Ctrl+C to copy")
        print("="*60)
        
        code = input("\nEnter the authorization code: ").strip()
        
        if not code:
            self.logger.error("❌ No authorization code provided")
            raise Exception("No authorization code provided")
        
        if not code.startswith("4/"):
            self.logger.warning("⚠️ Authorization code should start with '4/'")
            self.logger.info("   Make sure you copied the complete code")
        
        if len(code) < 20:
            self.logger.warning("⚠️ Authorization code seems too short")
            self.logger.info("   Make sure you copied the complete code")
        
        self.logger.info("🔄 Processing authorization code...")
        try:
            flow.fetch_token(code=code)
            return flow.credentials
        except Exception as manual_error:
            error_msg = str(manual_error).lower()
            if "access_denied" in error_msg or "403" in error_msg:
                self.logger.error("❌ OAuth access denied (Error 403)")
                self.logger.info("💡 This usually means:")
                self.logger.info("   • Your email is not added as a test user")
                self.logger.info("   • Go to Google Cloud Console > OAuth consent screen")
                self.logger.info("   • Add your email in 'Test users' section")
            else:
                self.logger.error(f"Manual OAuth failed: {manual_error}")
            raise manual_error
    
    def _show_oauth_setup_help(self):
        """Muestra ayuda para configurar OAuth 2.0"""
        self.logger.info("💡 Google Drive OAuth 2.0 setup steps:")
        self.logger.info("   1. Go to Google Cloud Console (console.cloud.google.com)")
        self.logger.info("   2. Create or select a project")
        self.logger.info("   3. Enable Google Drive API")
        self.logger.info("   4. Create OAuth 2.0 credentials:")
        self.logger.info("      • Application type: Desktop application")
        self.logger.info("      • Download JSON file")
        self.logger.info("   5. In 'OAuth consent screen' > 'Test users': Add your email")
        self.logger.info("   6. Save JSON as config/gdrive-credentials.json")
    
    def get_token_status(self) -> Dict[str, Any]:
        """Obtiene información del estado actual del token"""
        try:
            creds = self._load_existing_credentials()
            
            if not creds:
                return {
                    "exists": False,
                    "valid": False,
                    "has_refresh_token": False,
                    "message": "No token file found"
                }
            
            status = {
                "exists": True,
                "valid": creds.valid,
                "expired": creds.expired,
                "has_refresh_token": bool(creds.refresh_token),
                "auto_refresh_enabled": self.config.auto_refresh,
                "refresh_threshold_minutes": self.config.refresh_threshold_minutes
            }
            
            if creds.expiry:
                status["expires_at"] = creds.expiry.isoformat()
                time_to_expiry = (creds.expiry - datetime.now()).total_seconds()
                status["expires_in_seconds"] = max(0, time_to_expiry)
                status["expires_in_minutes"] = max(0, time_to_expiry / 60)
            
            # Determinar mensaje de estado
            if creds.valid:
                if creds.expiry:
                    time_to_expiry_min = (creds.expiry - datetime.now()).total_seconds() / 60
                    if time_to_expiry_min < self.config.refresh_threshold_minutes:
                        status["message"] = f"Token expires soon ({time_to_expiry_min:.1f}min) - will auto-refresh"
                    else:
                        status["message"] = f"Token valid for {time_to_expiry_min:.1f} more minutes"
                else:
                    status["message"] = "Token is valid"
            elif creds.refresh_token:
                status["message"] = "Token expired but can be refreshed automatically"
            else:
                status["message"] = "Token expired and no refresh token available - need re-authorization"
            
            return status
            
        except Exception as e:
            return {
                "exists": False,
                "valid": False,
                "has_refresh_token": False,
                "error": str(e),
                "message": f"Error checking token status: {e}"
            }
    
    def _test_connection(self) -> bool:
        """Prueba conexión con Google Drive"""
        try:
            # Hacer una llamada simple para verificar conexión
            about = self.service.about().get(fields="user").execute()
            user_email = about.get('user', {}).get('emailAddress', 'Unknown')
            
            # Enmascarar email para log seguro
            masked_email = self.secret_manager.mask_sensitive_data(user_email)
            self.logger.info(f"Connected as: {masked_email}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def upload(self, file_path: str) -> Optional[str]:
        """Sube archivo a Google Drive con validación automática de tokens"""
        try:
            if not self.service:
                self.logger.error("Not authenticated with Google Drive")
                return None
            
            # Validar credenciales antes de la operación crítica
            if not self._ensure_valid_credentials():
                self.logger.warning("Failed to ensure valid credentials, attempting re-authentication...")
                if not self.authenticate():
                    self.logger.error("Re-authentication failed")
                    return None
            
            # Asegurar que tenemos la carpeta de backup
            if not self.folder_id:
                self.folder_id = self._find_or_create_backup_folder()
                if not self.folder_id:
                    return None
            
            self.logger.progress("Uploading backup to Google Drive...", "📤")
            
            file_metadata = {
                'name': os.path.basename(file_path),
                'parents': [self.folder_id]
            }
            
            media = MediaFileUpload(
                file_path,
                mimetype='application/gzip',
                resumable=True
            )
            
            # Upload con progreso
            request = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,webViewLink'
            )
            
            file_obj = None
            while file_obj is None:
                status, file_obj = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"\r⬆️ Uploading... {progress}%", end='', flush=True)
            
            print()  # Nueva línea después del progreso
            
            self.logger.success("Backup uploaded to Google Drive")
            self.logger.info(f"📄 File: {file_obj.get('name')}")
            
            return file_obj.get('id')
            
        except Exception as e:
            self.logger.error(f"Upload failed: {e}")
            return None
    
    def _find_or_create_backup_folder(self) -> Optional[str]:
        """Encuentra o crea estructura de carpetas de backup (soporta rutas anidadas)"""
        try:
            # Dividir la ruta en partes para manejar carpetas anidadas
            folder_parts = self.config.folder.strip('/').split('/')
            current_parent_id = 'root'  # Empezar desde la raíz
            
            self.logger.info(f"Creating folder structure: {' > '.join(folder_parts)}")
            
            # Crear o encontrar cada carpeta en la jerarquía
            for i, folder_name in enumerate(folder_parts):
                folder_path = '/'.join(folder_parts[:i+1])
                
                # Buscar si la carpeta ya existe en el parent actual
                query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and '{current_parent_id}' in parents"
                results = self.service.files().list(
                    q=query,
                    fields="files(id, name)"
                ).execute()
                
                folders = results.get('files', [])
                
                if folders:
                    # Carpeta existe
                    current_parent_id = folders[0]['id']
                    self.logger.info(f"   📁 Found: {folder_path}")
                else:
                    # Crear nueva carpeta
                    self.logger.progress(f"Creating folder: {folder_path}...", "📁")
                    
                    folder_metadata = {
                        'name': folder_name,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [current_parent_id]
                    }
                    
                    folder = self.service.files().create(
                        body=folder_metadata,
                        fields='id'
                    ).execute()
                    
                    current_parent_id = folder.get('id')
                    self.logger.success(f"   📁 Created: {folder_path}")
            
            self.logger.success(f"Backup folder structure ready: '{self.config.folder}'")
            return current_parent_id
                
        except Exception as e:
            self.logger.error(f"Error managing backup folder: {e}")
            return None
    
    def configure_access(self, sharing_config: SharingConfig) -> bool:
        """Configura permisos de acceso"""
        try:
            if not sharing_config.emails and not sharing_config.make_public:
                self.logger.info("No sharing configuration - skipping", "ℹ️")
                return True
            
            if not self.folder_id:
                self.logger.error("No backup folder to configure access")
                return False
            
            permissions_created = []
            
            # Compartir con emails específicos
            for email in sharing_config.emails:
                try:
                    masked_email = self.secret_manager.mask_sensitive_data(email)
                    self.logger.info(f"Sharing with: {masked_email} (role: {sharing_config.role})", "📧")
                    
                    permission = {
                        'type': 'user',
                        'role': sharing_config.role,
                        'emailAddress': email
                    }
                    
                    self.service.permissions().create(
                        fileId=self.folder_id,
                        body=permission,
                        sendNotificationEmail=True
                    ).execute()
                    
                    permissions_created.append(f"✅ Shared with {masked_email} ({sharing_config.role})")
                    
                except Exception as e:
                    self.logger.warning(f"   ⚠️ Error sharing with {masked_email}: {e}")
                    permissions_created.append(f"❌ Error sharing with {masked_email}")
            
            # Hacer público si se solicita
            if sharing_config.make_public:
                try:
                    self.logger.progress("Making folder public...", "🌐")
                    
                    public_permission = {
                        'type': 'anyone',
                        'role': 'reader'  # Siempre reader para acceso público
                    }
                    
                    self.service.permissions().create(
                        fileId=self.folder_id,
                        body=public_permission
                    ).execute()
                    
                    permissions_created.append("✅ Folder is now public (read-only)")
                    
                except Exception as e:
                    self.logger.warning(f"Error making folder public: {e}")
                    permissions_created.append("❌ Error making folder public")
            
            # Obtener enlace de la carpeta
            try:
                folder_info = self.service.files().get(
                    fileId=self.folder_id,
                    fields='webViewLink'
                ).execute()
                
                folder_link = folder_info.get('webViewLink')
                
                self.logger.success("Access permissions configured:", "🔗")
                for permission in permissions_created:
                    self.logger.info(f"   {permission}")
                if folder_link:
                    self.logger.info(f"   📎 Link: {folder_link}")
                
            except Exception as e:
                self.logger.warning(f"Error getting folder link: {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error configuring access: {e}")
            return False
    
    def cleanup_old_files(self, retention_days: int) -> int:
        """Limpia archivos antiguos con validación de tokens"""
        try:
            # Validar credenciales antes de la operación
            if not self._ensure_valid_credentials():
                self.logger.warning("Failed to ensure valid credentials for cleanup")
                return 0
            
            self.logger.progress(f"Cleaning up old backups (>{retention_days} days)...", "🧹")
            
            if not self.folder_id:
                self.logger.warning("No backup folder for cleanup")
                return 0
            
            # Calcular fecha límite
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            cutoff_iso = cutoff_date.isoformat() + 'Z'
            
            # Buscar archivos antiguos en la carpeta de backup
            query = f"'{self.folder_id}' in parents and createdTime < '{cutoff_iso}'"
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, createdTime)"
            ).execute()
            
            old_files = results.get('files', [])
            
            if old_files:
                self.logger.info(f"Found {len(old_files)} old files to delete")
                
                deleted_count = 0
                for file_obj in old_files:
                    try:
                        self.service.files().delete(fileId=file_obj['id']).execute()
                        self.logger.info(f"   🗑️ Deleted: {file_obj['name']}")
                        deleted_count += 1
                    except Exception as e:
                        self.logger.warning(f"   ⚠️ Error deleting {file_obj['name']}: {e}")
                
                self.logger.success(f"Cleanup completed - deleted {deleted_count} files")
                return deleted_count
            else:
                self.logger.info("No old files found for cleanup", "ℹ️")
                return 0
                
        except Exception as e:
            self.logger.warning(f"Error during cleanup: {e}")
            return 0
