#!/bin/bash

# Script para limpiar directorios temporales huérfanos de wp-backup
# Ejecutar este script si hay directorios temporales que no se han limpiado

echo "🧹 Limpiando directorios temporales de wp-backup..."

# 1. Buscar directorios temporales huérfanos de TemporaryDirectory (wp_backup_*)
temp_dirs=$(find /tmp -maxdepth 1 -name "wp_backup_*" -type d 2>/dev/null || true)

# 2. Verificar directorio de backup local (/tmp/wp-backup)
wp_backup_dir="/tmp/wp-backup"

total_found=0
if [ -n "$temp_dirs" ]; then
    count=$(echo "$temp_dirs" | wc -l)
    total_found=$((total_found + count))
    echo "📂 Encontrados $count directorios wp_backup_*:"
    echo "$temp_dirs"
fi

if [ -d "$wp_backup_dir" ]; then
    total_found=$((total_found + 1))
    size=$(du -sh "$wp_backup_dir" 2>/dev/null | cut -f1)
    echo "📂 Encontrado directorio wp-backup: $wp_backup_dir ($size)"
fi

if [ $total_found -eq 0 ]; then
    echo "✅ No hay directorios temporales para limpiar"
    echo "📊 Espacio disponible en /tmp:"
    df -h /tmp | tail -1
    exit 0
fi

echo
echo "📊 Total encontrados: $total_found directorios"
read -p "¿Desea eliminar estos directorios? (y/N): " -r

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗑️  Eliminando directorios temporales..."
    
    # Limpiar wp_backup_* directories
    if [ -n "$temp_dirs" ]; then
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
    fi
    
    # Limpiar /tmp/wp-backup directory
    if [ -d "$wp_backup_dir" ]; then
        size=$(du -sh "$wp_backup_dir" 2>/dev/null | cut -f1)
        if rm -rf "$wp_backup_dir" 2>/dev/null; then
            echo "✅ Eliminado: wp-backup ($size)"
        else
            echo "❌ Error eliminando: wp-backup"
            echo "💡 Intenta: sudo rm -rf $wp_backup_dir"
        fi
    fi
    
    echo "✅ Limpieza completada"
else
    echo "❌ Limpieza cancelada"
fi

echo "📊 Espacio disponible en /tmp:"
df -h /tmp | tail -1
