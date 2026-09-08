from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def publish_service_event(service_id: int, event_type: str, status: int):
    """
    Publish a service state event to the service's channel group.
    Synchronous wrapper compatible with transaction.on_commit().
    """
    channel_layer = get_channel_layer()
    group_name = f"service_{service_id}"

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "service_event",
            "event_type": event_type,
            "service_id": service_id,
            "status": status,
        }
    )
