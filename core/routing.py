from django.urls import re_path

from .consumers import ServiceConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/services/(?P<service_id>\d+)/$",
        ServiceConsumer.as_asgi(),
    )
]
