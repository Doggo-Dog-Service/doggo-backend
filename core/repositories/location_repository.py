from asgiref.sync import sync_to_async

from ..models import ServiceLocation


class LocationRepository:
    """
    Responsável exclusivamente pelo acesso ao banco
    relacionado às localizações.
    """

    @staticmethod
    @sync_to_async
    def create(
        service,
        latitude,
        longitude,
    ):
        return ServiceLocation.objects.create(
            service=service,
            latitude=latitude,
            longitude=longitude,
        )
