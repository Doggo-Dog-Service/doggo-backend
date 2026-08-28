from django.urls import path

from .consumers import ServiceLocationConsumer

websocket_urlpatterns = [
    path(
        'ws/services/<int:service_id>/location/',
        ServiceLocationConsumer.as_asgi(),
    )
]