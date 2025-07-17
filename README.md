# WordPress Backup Tool 🚀

Una herramienta sencilla y **segura** para hacer backups de WordPress y subirlos automáticamente a Google Drive.

## ¿Por qué esta herramienta?

-   ✅ **Sin secretos en el código** - Todo se configura con variables de entorno
-   ✅ **OAuth 2.0** para Google Drive (más seguro que API keys)
-   ✅ **Súper simple** - Solo 4 comandos principales
-   ✅ **Limpieza automática** - Borra backups antiguos

## Instalación rápida

### Opción 1: Script automático (recomendado)

```bash
git clone <este-repo>
cd wp-backup
chmod +x install.sh
./install.sh
```

### Opción 2: Manual

```bash
git clone <este-repo>
cd wp-backup

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar
pip install -e .
wp-backup init
```

## Configuración

> **⚠️ Importante:** Si usas entorno virtual, actívalo antes de usar la herramienta:
>
> ```bash
> source venv/bin/activate
> ```

1. **Copia el archivo de ejemplo:**

    ```bash
    cp .env.example .env.local
    ```

2. **Edita `.env.local` con tus datos:**

    ```bash
    WP_DOMAIN=tudominio.com
    WP_PATH=/var/www/tudominio.com
    SHARE_EMAILS=tu@email.com
    ```

3. **Configura Google Drive:**
    - Ve a [Google Cloud Console](https://console.cloud.google.com/)
    - Crea credenciales OAuth 2.0 para "Desktop application"
    - **En "OAuth consent screen" > "Test users"**: Agrega tu email
    - Descarga el JSON y ponlo en `config/gdrive-credentials.json`
    
    **🔐 En VPS (autorización manual):**
    - La herramienta mostrará una URL
    - Ábrela en tu navegador (desde tu PC)
    - Autoriza la aplicación
    - Copia el código que aparece en pantalla
    - Pégalo en el VPS

## Uso

```bash
# Hacer backup
wp-backup backup

# Ver qué haría sin ejecutar
wp-backup backup --dry-run

# Probar que todo está bien configurado
wp-backup test

# Verificar seguridad
wp-backup security-scan
```

## Estructura del proyecto

```
src/
├── core/        # Lógica principal
├── providers/   # WordPress y Google Drive
├── security/    # Validaciones de seguridad
└── cli.py       # Comandos
```

## Requisitos

-   Python 3.8+
-   `mysqldump` (para la base de datos)
-   Cuenta de Google Drive

## ¿Problemas?

### Error común: "Acceso bloqueado: no ha completado el proceso de verificación"

```
Error 403: access_denied
```

**Solución:** En Google Cloud Console > OAuth consent screen > Test users: Agrega tu email

### Error: "Unable to connect" o "Firefox can't establish a connection to localhost"

Esto es **normal en VPS/servidores remotos**. El sistema intentará primero abrir un servidor local pero fallará (como debe ser). Automáticamente cambiará al flujo manual donde te dará una URL para autorizar desde tu navegador.

### Error: "¿De dónde saco el authorization code?"

Cuando autorices en el navegador, verás una página como esta:

```
Please copy this code, switch to your application and paste it there:

4/0AX4XfWi_example_code_here...
```

Copia TODO el código (empieza con `4/0A...`) y pégalo en el VPS.

### Otros problemas:

```bash
# Si algo falla, revisa la configuración
wp-backup test

# Verifica que no hay secretos en el código
wp-backup security-scan

# Si hay errores de módulos faltantes, actualiza el repo
git pull origin main
```

## Contribuir

1. Haz un fork
2. Crea tu rama: `git checkout -b mi-feature`
3. Haz tus cambios
4. Ejecuta: `wp-backup security-scan`
5. Pull request

## Licencia

MIT - Úsalo como quieras 😊

---

**¡Backups seguros y simples!** 🎯
