"""Helpers compartilhados pelos testes do fluxo de passeio."""

from contextlib import contextmanager
from datetime import time, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from core.models import ClientProfile, Pet, ProviderAvailability, ProviderProfile, Service, ServiceType

User = get_user_model()

SERVICE_DURATION_MINUTES = 60


@contextmanager
def raises(expected):
    """Equivalente enxuto de `pytest.raises` (pytest não é dependência): falha se `expected` não for levantada.

    Devolve um objeto cujo atributo `exception` guarda a exceção capturada.
    """
    caught = SimpleNamespace(exception=None)
    try:
        yield caught
    except expected as error:
        caught.exception = error
    assert caught.exception is not None, f'{expected.__name__} não foi levantada'


def make_user(email, *, full_name='Teste', phone=None, password='pw12345'):
    return User.objects.create_user(email=email, password=password, full_name=full_name, phone=phone)


def make_client(user):
    return ClientProfile.objects.create(user=user)


def make_service_type(name='Dog Walker', duration_minutes=SERVICE_DURATION_MINUTES):
    return ServiceType.objects.create(name=name, description=name, duration_minutes=duration_minutes)


def make_provider(user, *, service_type=None, price_per_hour=Decimal('60.00')):
    return ProviderProfile.objects.create(
        user=user,
        service_type=service_type or make_service_type(),
        fixed_latitude=Decimal('-27.5'),
        fixed_longitude=Decimal('-48.5'),
        price_per_hour=price_per_hour,
        is_active=True,
    )


def make_pet(owner, name='Bidu'):
    return Pet.objects.create(owner=owner, name=name, breed='Border Collie', size=Pet.Size.MEDIUM)


def make_service(client, provider, *, status=Service.Status.IN_REVIEW, start=None, pets=None):
    """Cria o serviço direto pelo ORM, sem validar agenda nem disponibilidade."""
    start = start or timezone.now() + timedelta(days=1)
    service = Service.objects.create(
        client=client,
        provider=provider,
        service_type=provider.service_type,
        start_datetime=start,
        end_datetime=start + timedelta(minutes=SERVICE_DURATION_MINUTES),
        status=status,
        price=Decimal('60.00'),
    )
    service.pets.set(pets if pets is not None else [make_pet(client)])
    return service


def add_availability(provider, on_date, start=time(0, 0), end=time(23, 59)):
    return ProviderAvailability.objects.create(
        provider=provider,
        weekday=on_date.weekday(),
        start_time=start,
        end_time=end,
    )


class FakeRedis:
    """Substituto em memória do cliente redis asyncio; `get` devolve bytes como o redis-py."""

    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ex=None):  # o TTL (ex) é aceito e ignorado de propósito
        if isinstance(value, str):
            value = value.encode()
        self.data[key] = value

    async def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)

    async def aclose(self):
        return None


class FlowTestCase(APITestCase):
    """Cenário base: tutor, passeador, um estranho sem perfis, um pet e um serviço em análise."""

    def setUp(self):
        cache.clear()
        self.tutor_user = make_user('tutor@test.com', full_name='Tutor', phone='47999990001')
        self.tutor = make_client(self.tutor_user)
        self.walker_user = make_user('walker@test.com', full_name='Passeador', phone='47999990002')
        self.walker = make_provider(self.walker_user)
        self.outsider_user = make_user('outsider@test.com', full_name='Estranho')
        self.pet = make_pet(self.tutor)
        self.service = make_service(self.tutor, self.walker, pets=[self.pet])

    def auth(self, user):
        self.client.force_authenticate(user=user)

    def action_url(self, service, name):
        return reverse(f'services-{name}', args=[service.pk])
