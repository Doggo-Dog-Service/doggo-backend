from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ClientProfile, Pet, ProviderAvailability, ProviderProfile, Service, ServiceType
from core.services import booking

User = get_user_model()

WALK_DURATION = 60
SITTER_DURATION = 120


def next_weekday(target_weekday, days_ahead=1):
    """Devolve a primeira data futura (a partir de `days_ahead`) com o weekday pedido."""
    result = booking.local_now().date() + timedelta(days=days_ahead)
    while result.weekday() != target_weekday:
        result += timedelta(days=1)
    return result


class SchedulingTestCase(APITestCase):
    def setUp(self):
        self.walker = ServiceType.objects.create(
            name='Dog Walker', description='Passeios', duration_minutes=WALK_DURATION
        )
        self.sitter = ServiceType.objects.create(
            name='Dog Sitter', description='Babá', duration_minutes=SITTER_DURATION
        )

        self.provider_user = User.objects.create_user(
            email='provider@test.com', password='pw12345', full_name='Ana Souza'
        )
        self.provider = ProviderProfile.objects.create(
            user=self.provider_user,
            fixed_latitude=Decimal('-27.5'),
            fixed_longitude=Decimal('-48.5'),
            service_type=self.walker,
            price_per_hour=Decimal('60.00'),
            is_active=True,
        )

        self.client_user = User.objects.create_user(email='client@test.com', password='pw12345', full_name='Bruno Lima')
        self.client_profile = ClientProfile.objects.create(user=self.client_user)

        self.other_user = User.objects.create_user(email='other@test.com', password='pw12345', full_name='Carla Dias')
        self.other_client = ClientProfile.objects.create(user=self.other_user)

        self.pet = Pet.objects.create(
            owner=self.client_profile, name='Bidu', breed='Border Collie', size=Pet.Size.MEDIUM
        )

        self.target_date = next_weekday(0, days_ahead=1)
        ProviderAvailability.objects.create(
            provider=self.provider,
            weekday=self.target_date.weekday(),
            start_time=time(9, 0),
            end_time=time(18, 0),
        )

        self.slots_url = reverse('availability-slots')

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def start_at(self, hour, minute=0, on_date=None):
        target = on_date or self.target_date
        return timezone.make_aware(datetime.combine(target, time(hour, minute)))


class SlotsEndpointTests(SchedulingTestCase):
    def test_nao_exige_duration_minutes_na_query(self):
        self.authenticate(self.client_user)

        response = self.client.get(self.slots_url, {'provider': self.provider.id, 'date': self.target_date.isoformat()})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['duration_minutes'] == WALK_DURATION
        assert 'available_slots' in response.data

    def test_usa_a_duracao_do_tipo_de_servico_do_prestador(self):
        self.provider.service_type = self.sitter
        self.provider.save()
        self.authenticate(self.client_user)

        response = self.client.get(self.slots_url, {'provider': self.provider.id, 'date': self.target_date.isoformat()})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['duration_minutes'] == SITTER_DURATION

    def test_lista_horarios_dentro_da_disponibilidade(self):
        self.authenticate(self.client_user)

        response = self.client.get(self.slots_url, {'provider': self.provider.id, 'date': self.target_date.isoformat()})

        assert response.status_code == status.HTTP_200_OK
        assert '09:00' in response.data['available_slots']
        assert '18:00' not in response.data['available_slots']

    def test_espaca_os_slots_pela_duracao_do_tipo_de_servico(self):
        self.provider.service_type = self.sitter
        self.provider.save()
        self.authenticate(self.client_user)

        response = self.client.get(self.slots_url, {'provider': self.provider.id, 'date': self.target_date.isoformat()})

        slots = response.data['available_slots']
        assert '09:00' in slots
        assert '10:00' not in slots
        assert '11:00' in slots

    def test_devolve_lista_vazia_sem_disponibilidade_no_dia(self):
        outro_dia = (self.target_date.weekday() + 1) % 7
        sem_disponibilidade = next_weekday(outro_dia, days_ahead=1)
        self.authenticate(self.client_user)

        response = self.client.get(
            self.slots_url,
            {'provider': self.provider.id, 'date': sem_disponibilidade.isoformat()},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['available_slots'] == []

    def test_exige_autenticacao(self):
        response = self.client.get(self.slots_url, {'provider': self.provider.id, 'date': self.target_date.isoformat()})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_exige_provider_e_data(self):
        self.authenticate(self.client_user)

        sem_provider = self.client.get(self.slots_url, {'date': self.target_date.isoformat()})
        sem_data = self.client.get(self.slots_url, {'provider': self.provider.id})

        assert sem_provider.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Informe o provider' in str(sem_provider.data)
        assert sem_data.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Informe a data' in str(sem_data.data)

    def test_rejeita_data_passada(self):
        ontem = booking.local_now().date() - timedelta(days=1)
        self.authenticate(self.client_user)

        response = self.client.get(self.slots_url, {'provider': self.provider.id, 'date': ontem.isoformat()})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_rejeita_tipo_de_servico_incompativel(self):
        self.authenticate(self.client_user)

        response = self.client.get(
            self.slots_url,
            {
                'provider': self.provider.id,
                'date': self.target_date.isoformat(),
                'service': self.sitter.id,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'incompatível' in str(response.data)


class ServiceCreationTests(SchedulingTestCase):
    def create_payload(self, **overrides):
        payload = {
            'pets': [self.pet.id],
            'provider': self.provider.id,
            'service_type': self.walker.id,
            'start_datetime': self.start_at(10).isoformat(),
        }
        payload.update(overrides)
        return payload

    def test_cria_servico_sem_informar_end_datetime(self):
        self.authenticate(self.client_user)

        response = self.client.post(reverse('services-list'), self.create_payload(), format='json')

        assert response.status_code == status.HTTP_201_CREATED

        service = Service.objects.get(pk=response.data['id'])
        assert service.end_datetime == self.start_at(10) + timedelta(minutes=WALK_DURATION)

    def test_deriva_a_duracao_do_tipo_de_servico(self):
        self.provider.service_type = self.sitter
        self.provider.save()
        self.authenticate(self.client_user)

        response = self.client.post(
            reverse('services-list'),
            self.create_payload(service_type=self.sitter.id),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        service = Service.objects.get(pk=response.data['id'])
        assert service.end_datetime == self.start_at(10) + timedelta(minutes=SITTER_DURATION)

    def test_calcula_o_preco_a_partir_do_horario_final_derivado(self):
        self.authenticate(self.client_user)

        response = self.client.post(reverse('services-list'), self.create_payload(), format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert str(response.data['price']) == '60.00'

    def test_respeita_end_datetime_informado_explicitamente(self):
        self.authenticate(self.client_user)

        response = self.client.post(
            reverse('services-list'),
            self.create_payload(end_datetime=self.start_at(12).isoformat()),
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED

        service = Service.objects.get(pk=response.data['id'])
        assert service.end_datetime == self.start_at(12)

    def test_rejeita_provider_agendando_consigo_mesmo(self):
        self.authenticate(self.provider_user)

        response = self.client.post(reverse('services-list'), self.create_payload(), format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_rejeita_pet_de_outro_cliente(self):
        outro_pet = Pet.objects.create(owner=self.other_client, name='Thor', breed=None, size=Pet.Size.LARGE)
        self.authenticate(self.client_user)

        response = self.client.post(reverse('services-list'), self.create_payload(pets=[outro_pet.id]), format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'seus pets' in str(response.data)

    def test_exige_ao_menos_um_pet(self):
        self.authenticate(self.client_user)

        response = self.client.post(reverse('services-list'), self.create_payload(pets=[]), format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_rejeita_horario_fora_da_disponibilidade(self):
        self.authenticate(self.client_user)

        response = self.client.post(
            reverse('services-list'),
            self.create_payload(start_datetime=self.start_at(7).isoformat()),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'não está disponível' in str(response.data)

    def test_rejeita_inicio_no_passado(self):
        ontem = booking.local_now() - timedelta(days=1)
        inicio = timezone.make_aware(datetime.combine(ontem.date(), time(10, 0)))
        self.authenticate(self.client_user)

        response = self.client.post(
            reverse('services-list'),
            self.create_payload(start_datetime=inicio.isoformat()),
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'futuro' in str(response.data)

    def test_devolve_409_quando_o_horario_ja_esta_ocupado(self):
        ocupado_inicio = self.start_at(10)
        ocupado = Service.objects.create(
            client=self.client_profile,
            provider=self.provider,
            service_type=self.walker,
            start_datetime=ocupado_inicio,
            end_datetime=ocupado_inicio + timedelta(minutes=WALK_DURATION),
            status=Service.Status.CONFIRMED,
            price=Decimal('60.00'),
        )
        ocupado.pets.set([self.pet])
        self.authenticate(self.client_user)

        response = self.client.post(reverse('services-list'), self.create_payload(), format='json')

        assert response.status_code == status.HTTP_409_CONFLICT
