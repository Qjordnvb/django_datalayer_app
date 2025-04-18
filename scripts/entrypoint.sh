#!/bin/bash

set -e

# Función para esperar a que un servicio esté disponible
wait_for() {
    host="$1"
    port="$2"
    echo "Esperando a que $host:$port esté disponible..."

    i=0
    while ! nc -z "$host" "$port"; do
        i=$((i+1))
        if [ "$i" -gt 30 ]; then
            echo "Tiempo de espera agotado para $host:$port"
            exit 1
        fi
        sleep 1
    done

    echo "$host:$port está disponible"
}

# Esperar a servicios externos si se especifican
# (Mantenemos la lógica por si usas PG en el futuro)
if [ -n "$POSTGRES_HOST" ] && [ -n "$POSTGRES_PORT" ]; then
    wait_for "$POSTGRES_HOST" "$POSTGRES_PORT"
fi

# Esperar a Redis (importante para Channels si usa Redis)
if [ -n "$REDIS_HOST" ] && [ -n "$REDIS_PORT" ]; then
    wait_for "$REDIS_HOST" "$REDIS_PORT"
fi

# Aplicar migraciones
echo "Aplicando migraciones..."
python manage.py migrate --noinput

# Recopilar archivos estáticos
echo "Recopilando archivos estáticos..."
python manage.py collectstatic --noinput --clear

# Crear superusuario si no existe
# (Usamos DJANGO_SUPERUSER_PASSWORD como check principal)
if [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Intentando crear superusuario (ignorará si ya existe)..."
    python manage.py createsuperuser --noinput --username "${DJANGO_SUPERUSER_USERNAME:-admin}" --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" || true
fi

# ---- INICIO CAMBIO ----
# Ejecuta el comando pasado a 'docker run' o 'docker-compose run/up'
# En tu caso, ejecutará el "command: daphne..." de docker-compose.yml
echo "Iniciando proceso principal (CMD: $@)..."
exec "$@"
# ---- FIN CAMBIO ----

# Se elimina el if/else anterior que forzaba runserver o daphne basado en $1
