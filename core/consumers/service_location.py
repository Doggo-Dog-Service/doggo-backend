import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ObjectDoesNotExist
from redis.asyncio import Redis

from ..models import Service
from ..services import LocationService


class ServiceConsumer(AsyncWebsocketConsumer):

    MIN_LATITUDE = -90
    MIN_LONGITUDE = -180
    MAX_LATITUDE = 90
    MAX_LONGITUDE = 180

    async def connect(self):
        self.service_id = self.scope[
            "url_route"
        ]["kwargs"]["service_id"]

        self.group_name = (
            f"service_{self.service_id}"
        )

        user = self.scope["user"]

        if (
            isinstance(user, AnonymousUser)
            or not user.is_authenticated
        ):
            await self.close(code=4001)
            return

        try:
            self.service = await self._get_service()

        except ObjectDoesNotExist:
            await self.close(code=4004)
            return

        self.role = await self._get_user_role()

        if self.role is None:
            await self.close(code=4003)
            return

        self.redis = Redis.from_url(
            settings.REDIS_URL
        )

        self.location_service = LocationService(
            redis=self.redis
        )

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

        if hasattr(self, "redis"):
            await self.redis.aclose()

    async def receive(self, text_data):
        if self.role != "provider":
            await self.send_error(
                "Apenas o prestador pode enviar localização."
            )
            return

        try:
            data = json.loads(text_data)

        except json.JSONDecodeError:
            await self.send_error(
                "JSON inválido."
            )
            return

        message_type = data.get("type")

        if message_type != "location":
            await self.send_error(
                "Tipo de mensagem desconhecido."
            )
            return

        await self.handle_location(data)

    async def handle_location(self, data):
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        if latitude is None or longitude is None:
            await self.send_error(
                "Latitude e longitude são obrigatórias."
            )
            return

        try:
            latitude = float(latitude)
            longitude = float(longitude)

        except (TypeError, ValueError):
            await self.send_error(
                "Latitude e longitude devem ser números."
            )
            return

        if not self.MIN_LATITUDE <= latitude <= self.MAX_LATITUDE:
            await self.send_error(
                "Latitude inválida."
            )
            return

        if not self.MIN_LONGITUDE <= longitude <= self.MAX_LONGITUDE:
            await self.send_error(
                "Longitude inválida."
            )
            return

        location = await (
            self.location_service.process_location(
                service=self.service,
                latitude=latitude,
                longitude=longitude,
            )
        )

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "location_update",
                "location": location,
            },
        )

    async def location_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "location",
                    "location": event["location"],
                }
            )
        )

    async def service_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": event["event_type"],
                    "service_id": event["service_id"],
                    "status": event["status"],
                }
            )
        )

    async def send_error(self, message):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "error",
                    "message": message,
                }
            )
        )

    @sync_to_async
    def _get_service(self):
        return Service.objects.select_related(
            "provider__user",
            "client__user",
        ).get(
            id=self.service_id
        )

    @sync_to_async
    def _get_user_role(self):
        user = self.scope["user"]

        if self.service.provider.user == user:
            return "provider"

        if self.service.client.user == user:
            return "client"

        return None
