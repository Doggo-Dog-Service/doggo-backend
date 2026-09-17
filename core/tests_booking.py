"""Testes da Etapa 2 — agendamento (slots por data, solicitação, estados, preço, concorrência)."""

import threading
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.test import TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from core.models import ClientProfile, Pet, ProviderAvailability, ProviderProfile, Service, ServiceType, User
from core.services import booking

TZ = ZoneInfo('America/Sao_Paulo')


class BookingTestsBaseData:
    """Fixture builder compartilhado entre APITestCase e TransactionTestCase."""

    def _create_fixtures(self):
        self.service_type = ServiceType.objects.create(name='Dogwalking', description='Passeio com pets')
        self.other_service_type = ServiceType.objects.create(name='Dogsitter', description='Cuidado domiciliar')

        self.provider_user = self._make_user('provider@doggo.com', '11111111111')
        self.provider = self._create_provider(self.provider_user, price_per_hour=Decimal('25.00'))

        self.other_provider_user = self._make_user('otherprovider@doggo.com', '22222222222')
        self.other_provider = self._create_provider(
            self.other_provider_user,
            service_type=self.other_service_type,
            price_per_hour=Decimal('30.00'),
        )

        self.client_user = self._make_user('client@doggo.com', '33333333333')
        self.client_profile = ClientProfile.objects.create(user=self.client_user)
        self.pet = Pet.objects.create(owner=self.client_profile, name='Rex', size='m')
        self.pet2 = Pet.objects.create(owner=self.client_profile, name='Bob', size='g')

        self.other_client_user = self._make_user('otherclient@doggo.com', '44444444444')
        self.other_client_profile = ClientProfile.objects.create(user=self.other_client_user)
        self.other_pet = Pet.objects.create(owner=self.other_client_profile, name='Lucy', size='p')

        no_price_user = self._make_user('noprice@doggo.com', '55555555555')
        self.no_price_provider = self._create_provider(no_price_user, price_per_hour=None, price_per_day=None)

        day_price_user = self._make_user('dayprice@doggo.com', '66666666666')
        self.day_price_provider = self._create_provider(
            day_price_user,
            price_per_hour=None,
            price_per_day=Decimal('60.00'),
        )

        self.both_user = self._make_user('both@doggo.com', '77777777777')
        self.both_provider = self._create_provider(self.both_user, price_per_hour=Decimal('40.00'))
        self.both_client_profile = ClientProfile.objects.create(user=self.both_user)
        self.both_pet = Pet.objects.create(owner=self.both_client_profile, name='Zig', size='m')

        self._add_availability(self.provider, ProviderAvailability.Weekday.MONDAY, '07:00:00', '12:00:00')
        self._add_availability(self.provider, ProviderAvailability.Weekday.MONDAY, '14:00:00', '19:00:00')
        self._add_availability(self.no_price_provider, ProviderAvailability.Weekday.MONDAY, '07:00:00', '19:00:00')
        self._add_availability(self.day_price_provider, ProviderAvailability.Weekday.MONDAY, '07:00:00', '19:00:00')

    @staticmethod
    def _make_user(email, cpf):
        return User.objects.create_user(email=email, password='senha-123', cpf=cpf, full_name='Teste')

    def _create_provider(self, user, service_type=None, price_per_hour=None, price_per_day=None):
        return ProviderProfile.objects.create(
            user=user,
            fixed_latitude=Decimal('-23.550520'),
            fixed_longitude=Decimal('-46.633309'),
            service_type=service_type or self.service_type,
            price_per_hour=price_per_hour,
            price_per_day=price_per_day,
        )

    def _add_availability(self, provider, weekday, start, end):
        return ProviderAvailability.objects.create(
            provider=provider,
            weekday=weekday,
            start_time=start,
            end_time=end,
        )

    def _future_date_with_weekday(self, target_weekday):
        today = date.today()
        days = (target_weekday - today.weekday()) % 7 or 7
        return today + timedelta(days=days)

    def _dt(self, day, hour, minute=0):
        return datetime.combine(day, time(hour, minute), tzinfo=TZ)

    def _payload(self, **overrides):
        day = self._future_date_with_weekday(0)
        payload = {
            'pets': [self.pet.id],
            'provider': self.provider.id,
            'service_type': self.service_type.id,
            'start_datetime': self._dt(day, 9, 0).isoformat(),
            'end_datetime': self._dt(day, 10, 0).isoformat(),
        }
        payload.update(overrides)
        return payload

    def _make_service(self, status_value=Service.Status.IN_REVIEW, **overrides):
        day = self._future_date_with_weekday(0)
        defaults = {
            'pets': [self.pet],
            'provider': self.provider,
            'client': self.client_profile,
            'service_type': self.service_type,
            'start_datetime': self._dt(day, 9, 0),
            'end_datetime': self._dt(day, 10, 0),
            'status': status_value,
            'price': Decimal('25.00'),
        }
        defaults.update(overrides)
        pets = defaults.pop('pets')
        service = Service.objects.create(**defaults)
        service.pets.set(pets)
        return service


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class BookingTestsBase(BookingTestsBaseData, APITestCase):
    def setUp(self):
        self._create_fixtures()

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _post_service(self, payload, user=None):
        if user is not None:
            self._auth(user)
        return self.client.post('/api/services/', payload, format='json')

    def _slots_url(self, **params):
        query = urlencode({key: str(value) for key, value in params.items()})
        return f'/api/availability/slots/?{query}'


class AvailabilitySlotsTests(BookingTestsBase):
    def setUp(self):
        super().setUp()
        self.day = self._future_date_with_weekday(0)

    def test_slots_for_available_weekday(self):
        self._auth(self.client_user)
        url = self._slots_url(provider=self.provider.id, date=self.day.isoformat(), duration_minutes=60)
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK, response.data
        expected = ['07:00', '08:00', '09:00', '10:00', '11:00', '14:00', '15:00', '16:00', '17:00', '18:00']
        assert response.data['available_slots'] == expected

    def test_weekday_without_availability_returns_empty(self):
        tuesday = self._future_date_with_weekday(1)
        self._auth(self.client_user)
        url = self._slots_url(provider=self.provider.id, date=tuesday.isoformat(), duration_minutes=60)
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data['available_slots'] == []

    def test_slot_exceeding_interval_end_is_excluded(self):
        self._auth(self.client_user)
        url = self._slots_url(provider=self.provider.id, date=self.day.isoformat(), duration_minutes=120)
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data['available_slots'] == ['07:00', '09:00', '14:00', '16:00']
        assert '18:00' not in response.data['available_slots']

    def test_duration_respected(self):
        self._auth(self.client_user)
        one_hour = self.client.get(
            self._slots_url(provider=self.provider.id, date=self.day.isoformat(), duration_minutes=60)
        )
        two_hours = self.client.get(
            self._slots_url(provider=self.provider.id, date=self.day.isoformat(), duration_minutes=120)
        )
        assert one_hour.status_code == status.HTTP_200_OK
        assert two_hours.status_code == status.HTTP_200_OK
        assert one_hour.data['available_slots'] == [
            '07:00', '08:00', '09:00', '10:00', '11:00',
            '14:00', '15:00', '16:00', '17:00', '18:00',
        ]
        assert two_hours.data['available_slots'] == ['07:00', '09:00', '14:00', '16:00']

    def test_occupied_interval_is_removed(self):
        self._make_service(
            status_value=Service.Status.CONFIRMED,
            start_datetime=self._dt(self.day, 9, 0),
            end_datetime=self._dt(self.day, 10, 0),
        )
        self._auth(self.client_user)
        url = self._slots_url(provider=self.provider.id, date=self.day.isoformat(), duration_minutes=60)
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK, response.data
        assert '09:00' not in response.data['available_slots']
        assert '08:00' in response.data['available_slots']
        assert '10:00' in response.data['available_slots']

    def test_partial_overlap_removes_both_edges(self):
        self._make_service(
            status_value=Service.Status.CONFIRMED,
            start_datetime=self._dt(self.day, 8, 30),
            end_datetime=self._dt(self.day, 9, 30),
        )
        self._auth(self.client_user)
        url = self._slots_url(provider=self.provider.id, date=self.day.isoformat(), duration_minutes=60)
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK, response.data
        assert '08:00' not in response.data['available_slots']
        assert '09:00' not in response.data['available_slots']
        assert '07:00' in response.data['available_slots']
        assert '10:00' in response.data['available_slots']

    def test_multiple_intervals_same_day_are_combined(self):
        self._auth(self.client_user)
        url = self._slots_url(provider=self.provider.id, date=self.day.isoformat(), duration_minutes=60)
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK, response.data
        assert '11:00' in response.data['available_slots']
        assert '14:00' in response.data['available_slots']

    def test_cancelled_and_completed_do_not_block(self):
        self._make_service(
            status_value=Service.Status.CANCELLED,
            start_datetime=self._dt(self.day, 9, 0),
            end_datetime=self._dt(self.day, 10, 0),
        )
        self._auth(self.client_user)
        url = self._slots_url(provider=self.provider.id, date=self.day.isoformat(), duration_minutes=60)
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK, response.data
        assert '09:00' in response.data['available_slots']

    def test_past_date_returns_error(self):
        yesterday = date.today() - timedelta(days=1)
        self._auth(self.client_user)
        url = self._slots_url(provider=self.provider.id, date=yesterday.isoformat(), duration_minutes=60)
        response = self.client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_requires_authentication(self):
        url = self._slots_url(provider=self.provider.id, date=self.day.isoformat(), duration_minutes=60)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_params_return_error(self):
        self._auth(self.client_user)

        missing_provider = self.client.get(
            self._slots_url(date=self.day.isoformat(), duration_minutes=60)
        )
        assert missing_provider.status_code == status.HTTP_400_BAD_REQUEST

        invalid_date = self.client.get(
            self._slots_url(provider=self.provider.id, date='not-a-date', duration_minutes=60)
        )
        assert invalid_date.status_code == status.HTTP_400_BAD_REQUEST

        invalid_duration = self.client.get(
            self._slots_url(provider=self.provider.id, date=self.day.isoformat(), duration_minutes=0)
        )
        assert invalid_duration.status_code == status.HTTP_400_BAD_REQUEST

        nonexistent_provider = self.client.get(
            self._slots_url(provider=999999, date=self.day.isoformat(), duration_minutes=60)
        )
        assert nonexistent_provider.status_code == status.HTTP_404_NOT_FOUND

    def test_service_type_compatibility(self):
        self._auth(self.client_user)
        compatible = self.client.get(
            self._slots_url(
                provider=self.provider.id,
                date=self.day.isoformat(),
                duration_minutes=60,
                service=self.service_type.id,
            )
        )
        assert compatible.status_code == status.HTTP_200_OK

        incompatible = self.client.get(
            self._slots_url(
                provider=self.provider.id,
                date=self.day.isoformat(),
                duration_minutes=60,
                service=self.other_service_type.id,
            )
        )
        assert incompatible.status_code == status.HTTP_400_BAD_REQUEST

    def test_generate_slots_excludes_past_times(self):
        today = date.today()
        self._add_availability(self.provider, today.weekday(), '00:00:00', '23:00:00')
        slots = booking.generate_slots(self.provider, today, timedelta(minutes=60))
        now = booking.local_now()
        assert all(slot > now for slot in slots)


class ServiceRequestCreationTests(BookingTestsBase):
    def test_valid_creation(self):
        response = self._post_service(self._payload(), user=self.client_user)

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data['status'] == 1
        assert response.data['price'] == '25.00'
        assert response.data['client'] == self.client_profile.id

    def test_price_computed_for_fractional_hour(self):
        day = self._future_date_with_weekday(0)
        payload = self._payload(end_datetime=self._dt(day, 10, 30).isoformat())
        response = self._post_service(payload, user=self.client_user)

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data['price'] == '37.50'

    def test_multi_pet_service(self):
        payload = self._payload(pets=[self.pet.id, self.pet2.id])
        response = self._post_service(payload, user=self.client_user)

        assert response.status_code == status.HTTP_201_CREATED, response.data

    def test_provider_nonexistent(self):
        response = self._post_service(self._payload(provider=999999), user=self.client_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_service_type_nonexistent(self):
        response = self._post_service(self._payload(service_type=999999), user=self.client_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_service_type_of_another_provider(self):
        response = self._post_service(self._payload(service_type=self.other_service_type.id), user=self.client_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_pet_from_another_client(self):
        response = self._post_service(self._payload(pets=[self.other_pet.id]), user=self.client_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_past_date_rejected(self):
        past_monday = date.today() - timedelta(days=7)
        payload = self._payload(
            start_datetime=self._dt(past_monday, 9, 0).isoformat(),
            end_datetime=self._dt(past_monday, 10, 0).isoformat(),
        )
        response = self._post_service(payload, user=self.client_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_outside_availability_rejected(self):
        wednesday = self._future_date_with_weekday(2)
        payload = self._payload(
            start_datetime=self._dt(wednesday, 9, 0).isoformat(),
            end_datetime=self._dt(wednesday, 10, 0).isoformat(),
        )
        response = self._post_service(payload, user=self.client_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_duration_exceeding_interval_rejected(self):
        day = self._future_date_with_weekday(0)
        payload = self._payload(
            start_datetime=self._dt(day, 11, 30).isoformat(),
            end_datetime=self._dt(day, 13, 0).isoformat(),
        )
        response = self._post_service(payload, user=self.client_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_end_datetime_required(self):
        payload = self._payload()
        payload.pop('end_datetime')
        response = self._post_service(payload, user=self.client_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_end_before_start_rejected(self):
        day = self._future_date_with_weekday(0)
        payload = self._payload(
            start_datetime=self._dt(day, 10, 0).isoformat(),
            end_datetime=self._dt(day, 9, 0).isoformat(),
        )
        response = self._post_service(payload, user=self.client_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_rejected(self):
        response = self.client.post('/api/services/', self._payload(), format='json')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_self_booking_rejected(self):
        payload = self._payload(
            provider=self.both_provider.id,
            pets=[self.both_pet.id],
        )
        response = self._post_service(payload, user=self.both_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_non_client_user_cannot_create(self):
        response = self._post_service(self._payload(), user=self.provider_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_conflicting_requests_are_rejected(self):
        first = self._post_service(self._payload(), user=self.client_user)
        assert first.status_code == status.HTTP_201_CREATED, first.data

        payload = self._payload(pets=[self.other_pet.id])
        second = self._post_service(payload, user=self.other_client_user)
        assert second.status_code == status.HTTP_409_CONFLICT, second.data

    def test_overlapping_requests_are_rejected(self):
        first = self._post_service(self._payload(), user=self.client_user)
        assert first.status_code == status.HTTP_201_CREATED, first.data

        day = self._future_date_with_weekday(0)
        payload = self._payload(
            pets=[self.other_pet.id],
            start_datetime=self._dt(day, 9, 30).isoformat(),
            end_datetime=self._dt(day, 10, 30).isoformat(),
        )
        second = self._post_service(payload, user=self.other_client_user)
        assert second.status_code == status.HTTP_409_CONFLICT, second.data

    def test_adjacent_requests_do_not_conflict(self):
        first = self._post_service(self._payload(), user=self.client_user)
        assert first.status_code == status.HTTP_201_CREATED, first.data

        day = self._future_date_with_weekday(0)
        payload = self._payload(
            pets=[self.other_pet.id],
            start_datetime=self._dt(day, 10, 0).isoformat(),
            end_datetime=self._dt(day, 11, 0).isoformat(),
        )
        second = self._post_service(payload, user=self.other_client_user)
        assert second.status_code == status.HTTP_201_CREATED, second.data


class ServiceStatusTransitionTests(BookingTestsBase):
    def _create_pending(self):
        payload = self._payload()
        return self._post_service(payload, user=self.client_user)

    def _action_url(self, pk, action_name):
        return f'/api/services/{pk}/{action_name}/'

    def test_initial_status_is_in_review(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED, created.data
        service = Service.objects.get(pk=created.data['id'])
        assert service.status == booking.IN_REVIEW_STATUS

    def test_provider_can_accept(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        response = self.client.post(self._action_url(created.data['id'], 'accept'))

        assert response.status_code == status.HTTP_200_OK, response.data
        service = Service.objects.get(pk=created.data['id'])
        assert service.status == booking.CONFIRMED_STATUS

    def test_wrong_provider_cannot_accept(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.other_provider_user)
        response = self.client.post(self._action_url(created.data['id'], 'accept'))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_client_cannot_accept(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        response = self.client.post(self._action_url(created.data['id'], 'accept'))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_accept_twice_is_conflict(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        first = self.client.post(self._action_url(created.data['id'], 'accept'))
        assert first.status_code == status.HTTP_200_OK, first.data

        second = self.client.post(self._action_url(created.data['id'], 'accept'))
        assert second.status_code == status.HTTP_409_CONFLICT, second.data

    def test_reject_by_provider(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        response = self.client.post(self._action_url(created.data['id'], 'reject'))

        assert response.status_code == status.HTTP_200_OK, response.data
        assert Service.objects.get(pk=created.data['id']).status == booking.REJECTED_STATUS

    def test_reject_when_confirmed_is_conflict(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        accepted = self.client.post(self._action_url(created.data['id'], 'accept'))
        assert accepted.status_code == status.HTTP_200_OK

        rejected = self.client.post(self._action_url(created.data['id'], 'reject'))
        assert rejected.status_code == status.HTTP_409_CONFLICT

    def test_client_cannot_reject(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        response = self.client.post(self._action_url(created.data['id'], 'reject'))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cancel_by_client(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.client_user)
        response = self.client.post(self._action_url(created.data['id'], 'cancel'))

        assert response.status_code == status.HTTP_200_OK, response.data
        assert Service.objects.get(pk=created.data['id']).status == booking.CANCELLED_STATUS

    def test_provider_cannot_cancel(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        response = self.client.post(self._action_url(created.data['id'], 'cancel'))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cancel_after_accept_is_conflict(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        accepted = self.client.post(self._action_url(created.data['id'], 'accept'))
        assert accepted.status_code == status.HTTP_200_OK

        self._auth(self.client_user)
        cancelled = self.client.post(self._action_url(created.data['id'], 'cancel'))
        assert cancelled.status_code == status.HTTP_409_CONFLICT

    def test_accept_revalidates_availability(self):
        wednesday = self._future_date_with_weekday(2)
        service = self._make_service(
            start_datetime=self._dt(wednesday, 9, 0),
            end_datetime=self._dt(wednesday, 10, 0),
        )

        self._auth(self.provider_user)
        response = self.client.post(self._action_url(service.pk, 'accept'))
        assert response.status_code == status.HTTP_409_CONFLICT, response.data

    def test_accept_revalidates_conflict(self):
        day = self._future_date_with_weekday(0)
        pending = self._make_service(
            start_datetime=self._dt(day, 10, 0),
            end_datetime=self._dt(day, 11, 0),
        )
        self._make_service(
            status_value=Service.Status.CONFIRMED,
            start_datetime=self._dt(day, 10, 30),
            end_datetime=self._dt(day, 11, 30),
        )

        self._auth(self.provider_user)
        response = self.client.post(self._action_url(pending.pk, 'accept'))
        assert response.status_code == status.HTTP_409_CONFLICT, response.data

    def test_finish_by_provider(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED
        service = Service.objects.get(pk=created.data['id'])
        service.status = Service.Status.IN_PROGRESS
        service.save(update_fields=['status'])

        self._auth(self.provider_user)
        response = self.client.post(self._action_url(service.pk, 'finish'))

        assert response.status_code == status.HTTP_200_OK, response.data
        assert Service.objects.get(pk=service.pk).status == booking.COMPLETED_STATUS

    def test_finish_when_not_in_progress_is_conflict(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        response = self.client.post(self._action_url(created.data['id'], 'finish'))
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_delete_pending_by_client(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.client_user)
        response = self.client.delete(f"/api/services/{created.data['id']}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Service.objects.filter(pk=created.data['id']).exists()

    def test_delete_accepted_is_conflict(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        accepted = self.client.post(self._action_url(created.data['id'], 'accept'))
        assert accepted.status_code == status.HTTP_200_OK

        self._auth(self.client_user)
        response = self.client.delete(f"/api/services/{created.data['id']}/")
        assert response.status_code == status.HTTP_409_CONFLICT

    def test_delete_by_non_owner_is_forbidden(self):
        created = self._create_pending()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.other_provider_user)
        response = self.client.delete(f"/api/services/{created.data['id']}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


class ServiceListTests(BookingTestsBase):
    def test_client_lists_only_own_services(self):
        self._post_service(self._payload(), user=self.client_user)
        self._make_service(
            client=self.other_client_profile,
            pets=[self.other_pet],
            provider=self.other_provider,
            service_type=self.other_service_type,
        )

        self._auth(self.client_user)
        response = self.client.get('/api/services/')

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['id'] == 1 or results[0]['client_id'] == self.client_profile.id

    def test_provider_lists_only_own_services(self):
        created = self._post_service(self._payload(), user=self.client_user)
        assert created.status_code == status.HTTP_201_CREATED
        self._make_service(
            client=self.other_client_profile,
            pets=[self.other_pet],
            provider=self.other_provider,
            service_type=self.other_service_type,
        )

        self._auth(self.provider_user)
        response = self.client.get('/api/services/')

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['provider_id'] == self.provider.id

    def test_list_filter_by_status(self):
        self._post_service(self._payload(), user=self.client_user)
        day = self._future_date_with_weekday(0)
        self._make_service(
            status_value=Service.Status.CONFIRMED,
            start_datetime=self._dt(day, 14, 0),
            end_datetime=self._dt(day, 15, 0),
        )

        self._auth(self.client_user)
        response = self.client.get('/api/services/?status=1')

        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['status'] == 1


class ServicePriceTests(BookingTestsBase):
    def test_price_tampering_is_ignored(self):
        payload = self._payload(price='0.01', provider=self.provider.id)
        response = self._post_service(payload, user=self.client_user)

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data['price'] == '25.00'
        assert Service.objects.get(pk=response.data['id']).price == Decimal('25.00')

    def test_provider_without_price_rejected(self):
        day = self._future_date_with_weekday(0)
        payload = self._payload(
            provider=self.no_price_provider.id,
            start_datetime=self._dt(day, 9, 0).isoformat(),
            end_datetime=self._dt(day, 10, 0).isoformat(),
        )
        response = self._post_service(payload, user=self.client_user)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'preço' in str(response.data)

    def test_price_per_day_used_when_no_hourly_price(self):
        day = self._future_date_with_weekday(0)
        payload = self._payload(
            provider=self.day_price_provider.id,
            start_datetime=self._dt(day, 9, 0).isoformat(),
            end_datetime=self._dt(day, 10, 0).isoformat(),
        )
        response = self._post_service(payload, user=self.client_user)

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data['price'] == '60.00'


class ServiceConcurrencyTests(BookingTestsBase):
    def test_two_clients_cannot_book_the_same_slot(self):
        first = self._post_service(self._payload(), user=self.client_user)
        assert first.status_code == status.HTTP_201_CREATED, first.data

        payload = self._payload(pets=[self.other_pet.id])
        second = self._post_service(payload, user=self.other_client_user)
        assert second.status_code == status.HTTP_409_CONFLICT, second.data

        assert Service.objects.count() == 1


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ServiceThreadedBookingTests(BookingTestsBaseData, TransactionTestCase):
    """Teste best-effort de concorrência real com threads.

    SQLite não suporta `SELECT ... FOR UPDATE` (no Django ele é ignorado); a
    serialização em dev vem do write-lock do banco inteiro + revalidação do
    conflito dentro da transação. Em PostgreSQL (candidato de produção) o
    `select_for_update` passa a valer de fato.
    """

    def setUp(self):
        super().setUp()
        self._create_fixtures()

    @staticmethod
    def _book_thread(barrier, results, user, payload, client):
        client.force_authenticate(user=user)
        barrier.wait()
        try:
            response = client.post('/api/services/', payload, format='json')
            results.append(response.status_code)
        except Exception as exc:  # pragma: no cover - ambiente de corrida variável
            results.append(type(exc).__name__)

    def test_simultaneous_requests_do_not_double_book(self):
        payload = self._payload()
        other_payload = self._payload(pets=[self.other_pet.id])

        barrier = threading.Barrier(2)
        results = []

        first_thread = threading.Thread(
            target=self._book_thread,
            args=(barrier, results, self.client_user, payload, APIClient()),
        )
        second_thread = threading.Thread(
            target=self._book_thread,
            args=(barrier, results, self.other_client_user, other_payload, APIClient()),
        )

        first_thread.start()
        second_thread.start()
        first_thread.join()
        second_thread.join()

        successful = sum(1 for result in results if result == status.HTTP_201_CREATED)
        assert successful <= 1, results
        day = self._future_date_with_weekday(0)
        services = Service.objects.filter(
            provider=self.provider,
            start_datetime=self._dt(day, 9, 0),
        )
        assert services.count() <= 1, results
