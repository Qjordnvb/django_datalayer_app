# Utilizar la imagen base de Playwright que ya incluye navegadores y otras dependencias
FROM mcr.microsoft.com/playwright:v1.40.0-jammy

# Establecer variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99

# Directorio de trabajo
WORKDIR /app

# Instalar xvfb, Python y otras dependencias necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    # xvfb y utilidades
    xvfb \
    netcat-traditional \
    xauth \
    # Python y pip
    python3 \
    python3-pip \
    python3-venv \
    # Dependencias comunes para navegadores headed en Debian/Ubuntu
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    libgdk-pixbuf2.0-0 \
    libatspi2.0-0 \
    libasound2 \
    # Limpiar caché de apt para mantener la imagen pequeña
 && rm -rf /var/lib/apt/lists/*

# Crear enlaces simbólicos para asegurarse de que pip y python estén disponibles
RUN ln -sf /usr/bin/python3 /usr/bin/python && \
    ln -sf /usr/bin/pip3 /usr/bin/pip

# Ahora podemos actualizar pip
RUN pip3 install --upgrade pip

# Copiar requirements.txt y instalar dependencias de Python
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# No necesitamos instalar los navegadores de Playwright porque ya están en la imagen base

# Copiar el código fuente
COPY . .

# Crear directorios para archivos estáticos y medios
RUN mkdir -p /app/staticfiles /app/media/uploads /app/media/reports /app/logs

# Permisos para los directorios
RUN chmod -R 755 /app/staticfiles /app/media /app/logs

# Script de inicio
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Puerto que expone la aplicación
EXPOSE 8000

# Script de inicio
ENTRYPOINT ["/entrypoint.sh"]
