"""Máquina de estados do passeio: quem pode mover o serviço de um status para outro.

Fluxo: Em análise -> Confirmado -> Em andamento -> Concluído, com Recusado (a partir de Em análise)
e Cancelado (a partir de Em análise ou Confirmado) como saídas. O ator é sempre o papel do usuário
*neste serviço*, nunca um papel global: o mesmo usuário pode ser tutor de um serviço e passeador de outro.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied

from core.models import ProviderProfile, Service
from core.services import booking
from core.services.service_events import publish_service_event
from core.utils.geo import path_distance

START_WINDOW = timedelta(minutes=30)

ACTOR_ERRORS = {
    'provider': 'Ação disponível apenas para o prestador',
    'client': 'Ação disponível apenas para o cliente',
    'any': 'Você não participa deste serviço',
}


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Conflito com outro agendamento'
    default_code = 'conflict'


def _require_actor(service, user, role):
    """Levanta 403 se `user` não tem o papel `role` ('provider', 'client' ou 'any') neste serviço."""
    allowed = (role in {'provider', 'any'} and service.provider.user_id == user.id) or (
        role in {'client', 'any'} and service.client.user_id == user.id
    )
    if not allowed:
        raise PermissionDenied(ACTOR_ERRORS[role])


def _require_status(service, allowed, message):
    if service.status not in allowed:
        raise Conflict(message)


def _lock(service):
    """Relê o serviço travando a linha (dentro de `transaction.atomic`), para decidir sobre o status atual."""
    return Service.objects.select_for_update().get(pk=service.pk)


def _publish_on_commit(service, event_type):
    """Agenda o evento para depois do commit: o WebSocket só avisa de transições que foram de fato gravadas."""
    service_id, service_status = service.pk, service.status
    transaction.on_commit(lambda: publish_service_event(service_id, event_type, service_status))


def confirm(service, user):
    _require_actor(service, user, 'provider')

    with transaction.atomic():
        provider = ProviderProfile.objects.select_for_update().get(pk=service.provider_id)
        service = _lock(service)
        _require_status(service, {Service.Status.IN_REVIEW}, 'Serviço não está pendente')
        if not booking.fits_in_availability(provider, service.start_datetime, service.end_datetime):
            raise Conflict('O horário não está mais disponível para este prestador')
        if booking.has_conflict(provider, service.start_datetime, service.end_datetime, exclude_pk=service.pk):
            raise Conflict('Horário em conflito com outro serviço')
        service.status = Service.Status.CONFIRMED
        service.save(update_fields=['status'])
        _publish_on_commit(service, 'walk_confirmed')

    return service


def reject(service, user):
    _require_actor(service, user, 'provider')

    with transaction.atomic():
        service = _lock(service)
        _require_status(service, {Service.Status.IN_REVIEW}, 'Serviço não está pendente')
        service.status = Service.Status.REJECTED
        service.save(update_fields=['status'])
        _publish_on_commit(service, 'walk_rejected')

    return service


def cancel(service, user):
    _require_actor(service, user, 'any')

    with transaction.atomic():
        service = _lock(service)
        _require_status(
            service,
            {Service.Status.IN_REVIEW, Service.Status.CONFIRMED},
            'Serviço não pode mais ser cancelado',
        )
        service.status = Service.Status.CANCELLED
        service.save(update_fields=['status'])
        _publish_on_commit(service, 'walk_cancelled')

    return service


def start(service, user, now=None):
    """Inicia o passeio: de `START_WINDOW` antes do início agendado até o fim agendado (inclusive)."""
    _require_actor(service, user, 'provider')
    now = now or timezone.now()

    with transaction.atomic():
        service = _lock(service)
        _require_status(service, {Service.Status.CONFIRMED}, 'Serviço não está confirmado')
        if now < service.start_datetime - START_WINDOW:
            minutes = START_WINDOW // timedelta(minutes=1)
            raise Conflict(f'Só é possível iniciar a partir de {minutes} minutos antes do horário agendado')
        if service.end_datetime is not None and now > service.end_datetime:
            raise Conflict('O horário agendado deste serviço já terminou')
        service.status = Service.Status.IN_PROGRESS
        service.started_at = now
        service.save(update_fields=['status', 'started_at'])
        _publish_on_commit(service, 'walk_started')

    return service


def complete(service, user):
    _require_actor(service, user, 'provider')

    with transaction.atomic():
        service = _lock(service)
        _require_status(service, {Service.Status.IN_PROGRESS}, 'Serviço não está em andamento')
        points = service.locations.order_by('created_at', 'pk').values_list('latitude', 'longitude')
        service.status = Service.Status.COMPLETED
        service.finished_at = timezone.now()
        service.distance_meters = path_distance(points)
        service.save(update_fields=['status', 'finished_at', 'distance_meters'])
        _publish_on_commit(service, 'walk_completed')

    return service
