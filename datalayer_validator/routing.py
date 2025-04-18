from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

import core.routing

application = ProtocolTypeRouter({
# HTTP -> Django views is added by default
'websocket': AllowedHostsOriginValidator(
AuthMiddlewareStack(
URLRouter(
core.routing.websocket_urlpatterns
)
)
),
})

