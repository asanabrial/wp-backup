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
        """Autentica con Google Drive usando OAuth 2.0 de forma segura"""
        try:
            creds = None
            
            # Cargar token existente
            if os.path.exists(self.TOKEN_FILE):
                try:
                    with open(self.TOKEN_FILE, 'rb') as token:
                        creds = pickle.load(token)
                except Exception as e:
                    self.logger.warning(f"Error loading existing token: {e}")
                    # Si hay error cargando token, continúa para regenerarlo
                    creds = None
            
            # Si no hay credenciales válidas, ejecutar flujo OAuth
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        self.logger.info("Refreshing access token...")
                        creds.refresh(Request())
                        self.logger.success("Access token refreshed")
                    except Exception as e:
                        self.logger.warning(f"Error refreshing token: {e}")
                        creds = None
                
                if not creds:
                    if not self._run_oauth_flow():
                        return False
                    
                    # Recargar credenciales después del flujo OAuth
                    if os.path.exists(self.TOKEN_FILE):
                        with open(self.TOKEN_FILE, 'rb') as token:
                            creds = pickle.load(token)
                    else:
                        self.logger.error("OAuth flow completed but no token file created")
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
    
    def _run_oauth_flow(self) -> bool:
        """Ejecuta flujo OAuth 2.0 de forma segura"""
        try:
            if not self.config.credentials_file.exists():
                self.logger.error(f"Credentials file not found: {self.config.credentials_file}")
                self._show_oauth_setup_help()
                return False
            
            self.logger.info("Starting OAuth 2.0 flow...")
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.config.credentials_file), self.SCOPES
            )
            
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
            # Guardar token para uso futuro
            with open(self.TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
            
            self.logger.success("OAuth 2.0 flow completed successfully")
            self.logger.info("Token saved for future use")
            
            return True
            
        except Exception as e:
            self.logger.error(f"OAuth flow failed: {e}")
            return False
    
    def _manual_oauth_flow(self, flow):
        """Ejecuta flujo OAuth manual para VPS/servidores"""
        # Para servidores sin navegador
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        print("\n" + "="*60)
        print("🔐 GOOGLE DRIVE AUTHORIZATION REQUIRED")
        print("="*60)
        print("⚠️ VPS/Remote server detected - using manual authorization")
        print()
        print("📱 On your computer/phone:")
        print(f"   1. Open: {auth_url}")
        print("   2. Sign in with Google")
        print("   3. Click 'Allow'")
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
        """Sube archivo a Google Drive"""
        try:
            if not self.service:
                self.logger.error("Not authenticated with Google Drive")
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
        """Encuentra o crea carpeta de backup"""
        try:
            # Buscar carpeta existente
            results = self.service.files().list(
                q=f"name='{self.config.folder}' and mimeType='application/vnd.google-apps.folder'",
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                folder_id = folders[0]['id']
                self.logger.success(f"Backup folder found: '{self.config.folder}'")
                return folder_id
            else:
                # Crear nueva carpeta
                self.logger.progress(f"Creating backup folder: '{self.config.folder}'...", "📁")
                
                folder_metadata = {
                    'name': self.config.folder,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                
                folder_id = folder.get('id')
                self.logger.success(f"Backup folder created: '{self.config.folder}'")
                
                return folder_id
                
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
        """Limpia archivos antiguos"""
        try:
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
