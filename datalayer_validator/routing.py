# datalayer_validator/routing.py
from django.urls import re_path
from core.consumers import BrowserConsumer

websocket_urlpatterns = [
    re_path(r"ws/browser/(?P<session_id>[^/]+)/$", BrowserConsumer.as_asgi()),
]
