# Logs Directory

Este directorio contiene los logs automáticos generados por los scripts de cron.

## Estructura de archivos

- `backup-YYYYMMDD-HHMMSS.log` - Logs de cada ejecución del backup
- Los logs se limpian automáticamente después de 30 días

## Ejemplo de contenido

```
2025-01-17 02:00:01 [INFO] WordPress Backup Tool - Automated Backup
2025-01-17 02:00:01 [INFO] Backing up: pequeaprendices.com
2025-01-17 02:00:01 [INFO] Google Drive folder: backup/pequeaprendices.com
2025-01-17 02:00:02 [SUCCESS] Backup completed successfully!
```
