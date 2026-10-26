# core/routing.py
from django.urls import re_path
from core.consumers import SurveillanceConsumer

websocket_urlpatterns = [
    re_path(r'ws/surveillance/alerts/$', SurveillanceConsumer.as_asgi()),
]