"""
Configuración ASGI para el proyecto datalayer_validator.

Expone el punto de entrada ASGI como una variable a nivel de módulo llamada ``application``.

Para obtener más información sobre este archivo, consulta
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
import django

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "datalayer_validator.settings")
django.setup()

# Importar las rutas de WebSocket después de configurar Django
import core.routing

# Aplicación ASGI con soporte para HTTP y WebSocket
application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                core.routing.websocket_urlpatterns
            )
        )
    ),
})
