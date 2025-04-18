# datalayer_validator/settings.py

"""
Configuraciones de Django para el proyecto DataLayer Validator Web.
"""

import os
from pathlib import Path
from django.utils.translation import gettext_lazy as _
from dotenv import load_dotenv # Para cargar variables de entorno desde .env

# Cargar variables de entorno desde .env (opcional pero recomendado)
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# Intenta obtenerla del entorno, si no, usa una clave insegura para desarrollo
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-fallback-key-for-dev')

# SECURITY WARNING: don't run with debug turned on in production!
# Convierte el valor de la variable de entorno a booleano
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Aplicaciones de terceros
    'channels',
    'crispy_forms',
    'crispy_bootstrap5',

    # Aplicaciones propias
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Para servir archivos estáticos eficiente
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'datalayer_validator.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Directorio de plantillas a nivel de proyecto
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# WSGI y ASGI
WSGI_APPLICATION = 'datalayer_validator.wsgi.application'
# Asegúrate que apunte a la aplicación ASGI definida en asgi.py
ASGI_APPLICATION = 'datalayer_validator.asgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
# Usando SQLite por defecto para desarrollo
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    { 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator', },
    { 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator', },
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/
LANGUAGE_CODE = 'es' # Cambiado a español

TIME_ZONE = 'UTC' # Mantener UTC para base de datos

USE_I18N = True

USE_TZ = True # Habilitar soporte de zona horaria


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/
STATIC_URL = '/static/'
# Directorio donde collectstatic reunirá los archivos estáticos para producción
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Directorios adicionales para buscar archivos estáticos
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
# Configuración para Whitenoise (servir estáticos en producción de forma simple)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Crispy Forms configuración
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# Configuración Channels
CHANNEL_LAYERS = {
    'default': {
        # Usar Redis si está disponible (mejor para producción y escalabilidad)
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            # Usar variables de entorno o el nombre del servicio Docker
             "hosts": [(os.environ.get('REDIS_HOST', 'redis'), int(os.environ.get('REDIS_PORT', 6379)))],
         },
        # O usar InMemory para desarrollo simple si Redis no está configurado
        # 'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# Configuración de Playwright (headless siempre False)
PLAYWRIGHT_SETTINGS = {
    'DEFAULT_BROWSER': 'chromium',  # 'chromium', 'firefox' o 'webkit'
    'HEADLESS': False, # <- CAMBIADO A False
    'VIEWPORT_SIZE': {
        'width': 1280,
        'height': 720
    },
    'SCREENSHOT_QUALITY': 80,  # Solo para JPEG
    'SCREENSHOT_TYPE': 'jpeg',  # 'png' o 'jpeg'
}

# Configuración de logging (Asegura que la ruta logs/ exista o tenga permisos)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module}:{lineno} {message}', # Añadido lineno
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO', # Más verboso en DEBUG
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            # Asegúrate que el directorio 'logs' exista y tenga permisos de escritura
            'filename': BASE_DIR / 'logs/datalayer_validator.log',
            'formatter': 'verbose',
            'encoding': 'utf-8', # Especificar encoding
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
         # Logger para tu aplicación 'core'
        'core': {
            'handlers': ['console', 'file'],
             'level': 'DEBUG' if DEBUG else 'INFO', # Nivel DEBUG para desarrollo
            'propagate': False, # No propagar a logger raíz si ya maneja console/file
        },
         # Logger específico para Channels/Daphne si necesitas más detalle
         'daphne': {
             'handlers': ['console', 'file'],
             'level': 'INFO',
         },
         'channels': {
              'handlers': ['console', 'file'],
              'level': 'INFO',
         },
    },
    # Puedes configurar el logger raíz si quieres capturar todo
    # 'root': {
    #     'handlers': ['console', 'file'],
    #     'level': 'INFO',
    # },
}

# Asegurarse de crear el directorio de logs si no existe
LOGS_DIR = BASE_DIR / 'logs'
if not LOGS_DIR.exists():
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Advertencia: No se pudo crear el directorio de logs: {LOGS_DIR}. Error: {e}")
