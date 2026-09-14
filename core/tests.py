from decimal import Decimal

from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import ClientProfile, ProviderAvailability, ProviderProfile, ServiceType, User


class ProviderAvailabilityAPITestsBase(APITestCase):
    def setUp(self):
        self.service_type = ServiceType.objects.create(name='Dogwalking', description='Passeio com pets')

        self.provider_user = self._create_user('provider@doggo.com', '11111111111')
        self.provider = self._create_provider(self.provider_user)

        self.other_provider_user = self._create_user('other@doggo.com', '22222222222')
        self.other_provider = self._create_provider(self.other_provider_user)

        self.client_user = self._create_user('client@doggo.com', '33333333333')
        self.client_profile = ClientProfile.objects.create(user=self.client_user)

    @staticmethod
    def _create_user(email, cpf):
        return User.objects.create_user(email=email, password='senha-123', cpf=cpf, full_name='Teste')

    def _create_provider(self, user):
        return ProviderProfile.objects.create(
            user=user,
            fixed_latitude=Decimal('-23.550520'),
            fixed_longitude=Decimal('-46.633309'),
            service_type=self.service_type,
            price_per_hour=Decimal('25.00'),
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _availability_url(self, pk=None):
        if pk is None:
            return '/api/availability/'
        return f'/api/availability/{pk}/'

    def _payload(self, **overrides):
        payload = {
            'weekday': ProviderAvailability.Weekday.MONDAY,
            'start_time': '07:00:00',
            'end_time': '19:00:00',
        }
        payload.update(overrides)
        return payload

    def _create_interval(self, **overrides):
        self._auth(self.provider_user)
        return self.client.post(self._availability_url(), self._payload(**overrides), format='json')


class ProviderAvailabilityCreationTests(ProviderAvailabilityAPITestsBase):
    def test_provider_can_create_valid_availability(self):
        response = self._create_interval()

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data['provider'] == self.provider.id
        assert response.data['weekday'] == ProviderAvailability.Weekday.MONDAY
        assert response.data['start_time'] == '07:00:00'
        assert response.data['end_time'] == '19:00:00'
        assert response.data['weekday_label'] == 'Segunda-feira'

    def test_create_provider_is_derived_from_request_user(self):
        response = self._create_interval(provider=self.other_provider.id)

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert response.data['provider'] == self.provider.id

    def test_create_availability_end_before_start(self):
        response = self._create_interval(start_time='19:00:00', end_time='07:00:00')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_availability_equal_times(self):
        response = self._create_interval(start_time='07:00:00', end_time='07:00:00')

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_duplicate_interval(self):
        first = self._create_interval()
        assert first.status_code == status.HTTP_201_CREATED

        response = self._create_interval()
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_overlapping_interval(self):
        first = self._create_interval(start_time='07:00:00', end_time='12:00:00')
        assert first.status_code == status.HTTP_201_CREATED

        response = self._create_interval(start_time='10:00:00', end_time='14:00:00')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_multiple_non_overlapping_intervals_same_weekday(self):
        first = self._create_interval(start_time='07:00:00', end_time='12:00:00')
        second = self._create_interval(start_time='14:00:00', end_time='19:00:00')

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_201_CREATED

    def test_create_without_provider_profile_rejected(self):
        self._auth(self.client_user)
        response = self.client.post(self._availability_url(), self._payload(), format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class ProviderAvailabilityConstraintTests(ProviderAvailabilityAPITestsBase):
    def test_model_rejects_end_lte_start(self):
        with self.assertRaises(IntegrityError):  # noqa: PT027
            ProviderAvailability.objects.create(
                provider=self.provider,
                weekday=ProviderAvailability.Weekday.MONDAY,
                start_time='19:00:00',
                end_time='07:00:00',
            )

    def test_model_rejects_exact_duplicate(self):
        ProviderAvailability.objects.create(
            provider=self.provider,
            weekday=ProviderAvailability.Weekday.MONDAY,
            start_time='07:00:00',
            end_time='19:00:00',
        )
        with self.assertRaises(IntegrityError):  # noqa: PT027
            ProviderAvailability.objects.create(
                provider=self.provider,
                weekday=ProviderAvailability.Weekday.MONDAY,
                start_time='07:00:00',
                end_time='19:00:00',
            )


class ProviderAvailabilityUpdateTests(ProviderAvailabilityAPITestsBase):
    def test_provider_can_update_own_availability(self):
        created = self._create_interval()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        response = self.client.patch(
            self._availability_url(created.data['id']),
            {'end_time': '20:00:00'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data['end_time'] == '20:00:00'
        assert response.data['start_time'] == '07:00:00'

    def test_update_excludes_own_instance_from_overlap_check(self):
        created = self._create_interval(start_time='07:00:00', end_time='12:00:00')
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        response = self.client.patch(
            self._availability_url(created.data['id']),
            {'start_time': '08:00:00', 'end_time': '11:00:00'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK, response.data

    def test_update_rejected_when_overlapping_another_interval(self):
        first = self._create_interval(start_time='07:00:00', end_time='12:00:00')
        assert first.status_code == status.HTTP_201_CREATED

        second = self._create_interval(start_time='14:00:00', end_time='19:00:00')
        assert second.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        response = self.client.patch(
            self._availability_url(second.data['id']),
            {'start_time': '09:00:00'},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_provider_cannot_update_other_provider_availability(self):
        created = self._create_interval()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.other_provider_user)
        response = self.client.patch(
            self._availability_url(created.data['id']),
            {'end_time': '20:00:00'},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_client_cannot_update_availability(self):
        created = self._create_interval()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.client_user)
        response = self.client.patch(
            self._availability_url(created.data['id']),
            {'end_time': '20:00:00'},
            format='json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class ProviderAvailabilityDeleteTests(ProviderAvailabilityAPITestsBase):
    def test_provider_can_delete_own_availability(self):
        created = self._create_interval()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        response = self.client.delete(self._availability_url(created.data['id']))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ProviderAvailability.objects.filter(pk=created.data['id']).exists()

    def test_provider_cannot_delete_other_provider_availability(self):
        created = self._create_interval()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.other_provider_user)
        response = self.client.delete(self._availability_url(created.data['id']))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_client_cannot_delete_availability(self):
        created = self._create_interval()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.client_user)
        response = self.client.delete(self._availability_url(created.data['id']))
        assert response.status_code == status.HTTP_403_FORBIDDEN


class ProviderAvailabilityQueryTests(ProviderAvailabilityAPITestsBase):
    def test_list_requires_authentication(self):
        response = self.client.get(self._availability_url())
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_filtered_by_provider_id(self):
        created_ids = []
        first = self._create_interval()
        assert first.status_code == status.HTTP_201_CREATED
        created_ids.append(first.data['id'])
        second = self._create_interval(weekday=ProviderAvailability.Weekday.TUESDAY)
        assert second.status_code == status.HTTP_201_CREATED
        created_ids.append(second.data['id'])

        self._auth(self.other_provider_user)
        other = self.client.post(
            self._availability_url(),
            self._payload(weekday=ProviderAvailability.Weekday.WEDNESDAY),
            format='json',
        )
        assert other.status_code == status.HTTP_201_CREATED

        self._auth(self.client_user)
        response = self.client.get(self._availability_url(), {'provider_id': self.provider.id})

        assert response.status_code == status.HTTP_200_OK
        assert {item['id'] for item in response.data} == set(created_ids)
        assert all(item['provider'] == self.provider.id for item in response.data)

    def test_provider_list_without_param_returns_only_own(self):
        created_ids = []
        first = self._create_interval()
        assert first.status_code == status.HTTP_201_CREATED
        created_ids.append(first.data['id'])
        second = self._create_interval(weekday=ProviderAvailability.Weekday.TUESDAY)
        assert second.status_code == status.HTTP_201_CREATED
        created_ids.append(second.data['id'])

        self._auth(self.other_provider_user)
        other = self.client.post(
            self._availability_url(),
            self._payload(weekday=ProviderAvailability.Weekday.WEDNESDAY),
            format='json',
        )
        assert other.status_code == status.HTTP_201_CREATED

        self._auth(self.provider_user)
        response = self.client.get(self._availability_url())

        assert response.status_code == status.HTTP_200_OK
        assert {item['id'] for item in response.data} == set(created_ids)

    def test_client_list_without_param_returns_empty(self):
        created = self._create_interval()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.client_user)
        response = self.client.get(self._availability_url())

        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_provider_without_availability_returns_empty_list(self):
        self._auth(self.other_provider_user)
        response = self.client.get(self._availability_url())

        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_retrieve_availability(self):
        created = self._create_interval()
        assert created.status_code == status.HTTP_201_CREATED

        self._auth(self.client_user)
        response = self.client.get(self._availability_url(created.data['id']))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == created.data['id']
        assert response.data['weekday_label'] == 'Segunda-feira'

    def test_provider_detail_includes_availability(self):
        created_ids = []
        first = self._create_interval()
        assert first.status_code == status.HTTP_201_CREATED
        created_ids.append(first.data['id'])
        second = self._create_interval(weekday=ProviderAvailability.Weekday.THURSDAY)
        assert second.status_code == status.HTTP_201_CREATED
        created_ids.append(second.data['id'])

        self._auth(self.client_user)
        response = self.client.get(f'/api/providers/{self.provider.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert {item['id'] for item in response.data['availability']} == set(created_ids)
        weekdays = {item['weekday'] for item in response.data['availability']}
        assert weekdays == {ProviderAvailability.Weekday.MONDAY, ProviderAvailability.Weekday.THURSDAY}
