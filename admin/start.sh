#!/bin/bash
# start.sh — Arranca la app en producción con Gunicorn
# Uso: bash start.sh
# Requiere: pip install -r requirements.txt

set -e

# Cargar variables de entorno desde .env
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

if [ -z "$SECRET_KEY" ]; then
  echo "ERROR: SECRET_KEY no está definida en .env"
  exit 1
fi

# Crear carpeta de logs si no existe
mkdir -p logs

echo "Iniciando Plantillas Web RD..."
exec gunicorn app:app \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --threads 2 \
  --timeout 60 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log \
  --log-level info \
  --preload
