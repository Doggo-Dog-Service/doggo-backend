from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt

from ..repositories import LocationRepository
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

        last_saved_location = (
            await self.redis_service.get_last_saved_location(
                service.id
            )
        )

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

        await self.redis_service.save_location(
            service.id,
            current_location,
        )

        return current_location

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
        distance = self._calculate_distance(
            last_saved_location["latitude"],
            last_saved_location["longitude"],
            current_location["latitude"],
            current_location["longitude"],
        )

        return distance >= self.SAVE_DISTANCE_METERS

    @staticmethod
    def _calculate_distance(
        latitude_1,
        longitude_1,
        latitude_2,
        longitude_2,
    ):
        earth_radius = 6371000

        latitude_1 = radians(latitude_1)
        latitude_2 = radians(latitude_2)

        delta_latitude = radians(
            latitude_2 - latitude_1
        )

        delta_longitude = radians(
            longitude_2 - longitude_1
        )

        a = (
            sin(delta_latitude / 2) ** 2
            + cos(latitude_1)
            * cos(latitude_2)
            * sin(delta_longitude / 2) ** 2
        )

        c = 2 * atan2(
            sqrt(a),
            sqrt(1 - a),
        )

        return earth_radius * c
