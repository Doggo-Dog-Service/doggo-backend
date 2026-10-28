import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def publish_service_event(service_id: int, event_type: str, status: int) -> None:
    """
    Publish a service state event to the service's channel group.
    Synchronous wrapper compatible with transaction.on_commit().

    Never raises: the status change is already committed when this runs, so a broker
    failure (e.g. Redis down) must not turn a successful transition into an error response.
    """
    try:
        channel_layer = get_channel_layer()
        group_name = f'service_{service_id}'

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'service_event',
                'event_type': event_type,
                'service_id': service_id,
                'status': status,
            },
        )
    except Exception:
        logger.exception('Falha ao publicar o evento %s do serviço %s', event_type, service_id)


def publish_walk_event(service_id: int, event: dict) -> None:
    """Publica um marcador do passeio no grupo do serviço. Nunca levanta (mesmo motivo de `publish_service_event`)."""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'service_{service_id}',
            {'type': 'walk_event_message', 'event': event},
        )
    except Exception:
        logger.exception('Falha ao publicar o marcador do serviço %s', service_id)
