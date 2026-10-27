import json
import logging
from contextlib import closing

import redis
import redis.asyncio
from django.conf import settings

logger = logging.getLogger(__name__)

_shared_redis = None


def get_shared_redis() -> redis.asyncio.Redis:
    """Cliente Redis assíncrono único por processo, criado na primeira chamada.

    O cliente tem um pool de conexões próprio e é seguro para uso concorrente; os consumers do WebSocket o
    compartilham em vez de abrir (e fechar) uma conexão por socket. `from_url` não conecta: a conexão só é aberta
    no primeiro comando.
    """
    global _shared_redis  # noqa: PLW0603
    if _shared_redis is None:
        _shared_redis = redis.asyncio.Redis.from_url(settings.REDIS_URL)
    return _shared_redis


class RedisService:
    """
    Responsável pelo armazenamento temporário das
    localizações e informações do serviço no Redis.
    """

    LOCATION_TTL = 60 * 60

    def __init__(self, redis):
        self.redis = redis

    @staticmethod
    def get_location_key(service_id):
        return f"doggo:service:{service_id}:location"

    @staticmethod
    def get_saved_location_key(service_id):
        return f"doggo:service:{service_id}:saved_location"

    @staticmethod
    def get_distance_key(service_id):
        return f"doggo:service:{service_id}:distance"

    async def get_last_location(self, service_id):
        return await self._get(
            self.get_location_key(service_id)
        )

    async def save_location(
        self,
        service_id,
        location,
    ):
        await self._save(
            self.get_location_key(service_id),
            location,
        )

    async def get_last_saved_location(self, service_id):
        return await self._get(
            self.get_saved_location_key(service_id)
        )

    async def save_saved_location(
        self,
        service_id,
        location,
    ):
        await self._save(
            self.get_saved_location_key(service_id),
            location,
        )

    async def get_distance(self, service_id):
        distance = await self.redis.get(
            self.get_distance_key(service_id)
        )

        if distance is None:
            return None

        if isinstance(distance, bytes):
            distance = distance.decode("utf-8")

        return float(distance)

    async def save_distance(
        self,
        service_id,
        distance,
    ):
        await self.redis.set(
            self.get_distance_key(service_id),
            distance,
            ex=self.LOCATION_TTL,
        )

    async def delete_location(self, service_id):
        await self.redis.delete(
            self.get_location_key(service_id)
        )

    async def delete_saved_location(self, service_id):
        await self.redis.delete(
            self.get_saved_location_key(service_id)
        )

    async def delete_distance(self, service_id):
        await self.redis.delete(
            self.get_distance_key(service_id)
        )

    async def _get(self, key):
        location = await self.redis.get(key)

        if not location:
            return None

        if isinstance(location, bytes):
            location = location.decode("utf-8")

        return json.loads(location)

    async def _save(self, key, location):
        await self.redis.set(
            key,
            json.dumps(location),
            ex=self.LOCATION_TTL,
        )


def clear_service_location(service_id: int) -> None:
    """Apaga do Redis a localização e a distância temporárias do serviço, de forma síncrona.

    Roda depois do commit (`transaction.on_commit`), quando o passeio já foi concluído: uma falha do Redis
    é só registrada em log, nunca propagada, para não transformar uma conclusão gravada em erro de resposta.
    """
    try:
        with closing(redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)) as client:
            client.delete(
                RedisService.get_location_key(service_id),
                RedisService.get_saved_location_key(service_id),
                RedisService.get_distance_key(service_id),
            )
    except Exception:
        logger.exception('Falha ao limpar a localização do serviço %s no Redis', service_id)
