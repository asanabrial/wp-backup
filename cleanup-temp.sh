#!/bin/bash

# Script para limpiar directorios temporales huérfanos de wp-backup
# Ejecutar este script si hay directorios temporales que no se han limpiado

echo "🧹 Limpiando directorios temporales de wp-backup..."

# Buscar directorios temporales huérfanos
temp_dirs=$(find /tmp -maxdepth 1 -name "wp_backup_*" -type d 2>/dev/null || true)

if [ -n "$temp_dirs" ]; then
    count=$(echo "$temp_dirs" | wc -l)
    echo "📂 Encontrados $count directorios temporales:"
    echo "$temp_dirs"
    echo
    
    read -p "¿Desea eliminar estos directorios? (y/N): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Eliminando directorios temporales..."
        echo "$temp_dirs" | while read -r dir; do
            if [ -n "$dir" ] && [ -d "$dir" ]; then
                size=$(du -sh "$dir" 2>/dev/null | cut -f1)
                if rm -rf "$dir" 2>/dev/null; then
                    echo "✅ Eliminado: $(basename "$dir") ($size)"
                else
                    echo "❌ Error eliminando: $(basename "$dir")"
                fi
            fi
        done
        echo "✅ Limpieza completada"
    else
        echo "❌ Limpieza cancelada"
    fi
else
    echo "✅ No hay directorios temporales para limpiar"
fi

echo "📊 Espacio disponible en /tmp:"
df -h /tmp | tail -1
