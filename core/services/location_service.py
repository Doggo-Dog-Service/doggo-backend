from datetime import datetime, timezone

from ..repositories import LocationRepository
from ..utils.geo import haversine
from .redis_service import RedisService


class LocationService:

    SAVE_INTERVAL_SECONDS = 10
    SAVE_DISTANCE_METERS = 10

    def __init__(self, redis):
        self.redis_service = RedisService(redis)
        self.location_repository = LocationRepository()

    async def process_location(
        self,
        service,
        latitude,
        longitude,
    ):
        current_location = {
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        # Última localização recebida pelo WebSocket.
        last_location = (
            await self.redis_service.get_last_location(
                service.id
            )
        )

        # Última localização persistida no banco.
        last_saved_location = (
            await self.redis_service.get_last_saved_location(
                service.id
            )
        )

        # Calcula e atualiza a distância percorrida.
        distance = await self._process_distance(
            service.id,
            last_location,
            current_location,
        )

        # Verifica se a localização atual deve
        # ser persistida no banco.
        should_save = await self._should_save_location(
            last_saved_location,
            current_location,
        )

        if should_save:
            await self.location_repository.create(
                service=service,
                latitude=latitude,
                longitude=longitude,
            )

            await self.redis_service.save_saved_location(
                service.id,
                current_location,
            )

        # Atualiza a última localização recebida.
        await self.redis_service.save_location(
            service.id,
            current_location,
        )

        return {
            "location": current_location,
            "distance": distance,
        }

    async def _process_distance(
        self,
        service_id,
        last_location,
        current_location,
    ):
        """
        Calcula a distância entre a última localização
        recebida e a localização atual e adiciona esse
        trecho à distância total do passeio.
        """

        # Primeiro ponto do passeio.
        if last_location is None:
            distance = 0.0

            await self.redis_service.save_distance(
                service_id,
                distance,
            )

            return distance

        # Recupera a distância acumulada.
        distance = (
            await self.redis_service.get_distance(
                service_id
            )
        )

        # Caso a chave não exista no Redis,
        # inicia a distância em zero.
        if distance is None:
            distance = 0.0

        # Calcula somente o trecho entre o último
        # ponto recebido e o ponto atual.
        segment_distance = haversine(
            last_location["latitude"],
            last_location["longitude"],
            current_location["latitude"],
            current_location["longitude"],
        )

        # Adiciona o novo trecho à distância total.
        distance += segment_distance

        # Atualiza a distância acumulada no Redis.
        await self.redis_service.save_distance(
            service_id,
            distance,
        )

        return distance

    async def _should_save_location(
        self,
        last_saved_location,
        current_location,
    ):
        if last_saved_location is None:
            return True

        if self._has_elapsed_required_time(
            last_saved_location,
            current_location,
        ):
            return True

        if self._has_moved_required_distance(
            last_saved_location,
            current_location,
        ):
            return True

        return False

    def _has_elapsed_required_time(
        self,
        last_saved_location,
        current_location,
    ):
        last_timestamp = datetime.fromisoformat(
            last_saved_location["timestamp"]
        )

        current_timestamp = datetime.fromisoformat(
            current_location["timestamp"]
        )

        elapsed_seconds = (
            current_timestamp - last_timestamp
        ).total_seconds()

        return (
            elapsed_seconds
            >= self.SAVE_INTERVAL_SECONDS
        )

    def _has_moved_required_distance(
        self,
        last_saved_location,
        current_location,
    ):
        distance = haversine(
            last_saved_location["latitude"],
            last_saved_location["longitude"],
            current_location["latitude"],
            current_location["longitude"],
        )

        return distance >= self.SAVE_DISTANCE_METERS
