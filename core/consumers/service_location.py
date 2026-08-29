import json

from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.exceptions import ObjectDoesNotExist
from redis.asyncio import Redis

from ..models import Service
from ..services import LocationService


class ServiceConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.service_id = self.scope["url_route"]["kwargs"]["service_id"]

        self.group_name = (
            f"service_{self.service_id}"
        )

        self.redis = Redis.from_url(
            self._get_redis_url()
        )

        self.location_service = LocationService(
            redis=self.redis
        )

        try:
            self.service = await self._get_service()

        except ObjectDoesNotExist:
            await self.close(code=4004)
            return

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
            await self.redis.close()

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)

        except json.JSONDecodeError:
            await self.send_error(
                "JSON inválido."
            )
            return

        message_type = data.get("type")

        if message_type == "location":
            await self.handle_location(data)
            return

        await self.send_error(
            "Tipo de mensagem desconhecido."
        )

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

        location = await self.location_service.process_location(
            service=self.service,
            latitude=latitude,
            longitude=longitude,
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

    async def send_error(self, message):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "error",
                    "message": message,
                }
            )
        )

    async def _get_service(self):
        from asgiref.sync import sync_to_async  # noqa: PLC0415

        return await sync_to_async(
            Service.objects.select_related(
                "provider"
            ).get
        )(
            id=self.service_id
        )

    @staticmethod
    def _get_redis_url():
        from django.conf import settings  # noqa: PLC0415

        return settings.REDIS_URL
