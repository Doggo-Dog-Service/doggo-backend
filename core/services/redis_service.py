import json


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
