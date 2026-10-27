from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status

from core.models import Service
from core.serializers import service as service_serializers
from core.tests.helpers import (
    add_availability,
    make_client,
    make_pet,
    make_provider,
    make_service,
    make_user,
)
from core.tests.test_service_flow import ServiceFlowTestCase
from uploader.models import Image

SERVICES_PER_LIST = 5
WALKER_PHONE = '47999990002'
TUTOR_PHONE = '47999990001'
ONE_HOUR = timedelta(hours=1)
SAVED_DISTANCE = 1234.5678
ROUNDED_DISTANCE = 1234.57


def list_url():
    return reverse('services-list')


def detail_url(service):
    return reverse('services-detail', args=[service.pk])


def make_picture(name):
    return Image.objects.create(file=f'images/{name}.jpg')


class ServiceAccessTestCase(ServiceFlowTestCase):
    def results(self, user, params=None):
        self.auth(user)
        response = self.client.get(list_url(), params)
        assert response.status_code == status.HTTP_200_OK
        return response.data['results']


class ServiceQuerysetTests(ServiceAccessTestCase):
    def test_retrieve_por_nao_participante_da_404(self):
        self.auth(self.outsider_user)

        response = self.client.get(detail_url(self.service))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_por_outro_tutor_da_404(self):
        other_user = make_user('other@test.com')
        make_client(other_user)
        self.auth(other_user)

        response = self.client.get(detail_url(self.service))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_pelo_tutor_e_pelo_passeador_da_200(self):
        for user in (self.tutor_user, self.walker_user):
            with self.subTest(user=user.email):
                self.auth(user)

                response = self.client.get(detail_url(self.service))

                assert response.status_code == status.HTTP_200_OK
                assert response.data['id'] == self.service.pk

    def test_sem_login_da_401(self):
        response = self.client.get(list_url())

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_lista_de_usuario_sem_perfil_vem_vazia(self):
        assert self.results(self.outsider_user) == []

    def test_lista_so_traz_servicos_dos_quais_o_usuario_participa(self):
        other_user = make_user('other@test.com')
        other_client = make_client(other_user)
        other_service = make_service(other_client, make_provider(make_user('other-walker@test.com')))

        assert [item['id'] for item in self.results(self.tutor_user)] == [self.service.pk]
        assert [item['id'] for item in self.results(self.walker_user)] == [self.service.pk]
        assert [item['id'] for item in self.results(other_user)] == [other_service.pk]

    def test_lista_vem_do_mais_novo_para_o_mais_antigo(self):
        newer = make_service(self.tutor, self.walker, pets=[self.pet])

        ids = [item['id'] for item in self.results(self.tutor_user)]

        assert ids == [newer.pk, self.service.pk]

    def test_filtro_de_status_na_lista(self):
        confirmed = make_service(self.tutor, self.walker, status=Service.Status.CONFIRMED, pets=[self.pet])

        ids = [item['id'] for item in self.results(self.tutor_user, {'status': Service.Status.CONFIRMED})]

        assert ids == [confirmed.pk]

    def test_filtros_de_prestador_e_cliente_na_lista(self):
        other_walker = make_provider(make_user('other-walker@test.com'))
        other = make_service(self.tutor, other_walker, pets=[self.pet])

        by_provider = self.results(self.tutor_user, {'provider': other_walker.pk})
        by_client = self.results(self.walker_user, {'client': self.tutor.pk})
        by_wrong_client = self.results(self.walker_user, {'client': self.tutor.pk + 1000})

        assert [item['id'] for item in by_provider] == [other.pk]
        assert [item['id'] for item in by_client] == [self.service.pk]
        assert by_wrong_client == []

    def test_filtro_nao_numerico_na_lista_da_400(self):
        self.auth(self.tutor_user)

        for param in ('status', 'provider', 'client'):
            with self.subTest(param=param):
                response = self.client.get(list_url(), {param: 'abc'})

                assert response.status_code == status.HTTP_400_BAD_REQUEST
                assert param in response.data

    def test_filtro_com_numero_gigante_vem_vazio(self):
        assert self.results(self.tutor_user, {'status': '9' * 40}) == []

    def test_filtros_nao_valem_em_rotas_de_detalhe(self):
        add_availability(self.walker, self.start.date())
        self.auth(self.tutor_user)
        retrieve = self.client.get(detail_url(self.service), {'status': 'abc', 'provider': 'x'})
        self.auth(self.walker_user)
        confirm = self.client.post(self.action_url(self.service, 'confirm') + '?status=2&client=999')

        assert retrieve.status_code == status.HTTP_200_OK
        assert confirm.status_code == status.HTTP_200_OK
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.CONFIRMED


class ServiceMethodsTests(ServiceAccessTestCase):
    def test_delete_retorna_405(self):
        for user in (self.tutor_user, self.walker_user, self.outsider_user):
            with self.subTest(user=user.email):
                self.auth(user)

                response = self.client.delete(detail_url(self.service))

                assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert Service.objects.filter(pk=self.service.pk).exists()

    def test_put_retorna_405(self):
        self.auth(self.tutor_user)

        response = self.client.put(detail_url(self.service), {'start_datetime': self.start.isoformat()}, format='json')

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_schema_nao_anuncia_put_nem_delete(self):
        self.auth(self.tutor_user)

        response = self.client.get(reverse('schema'), {'format': 'json'})

        detail = response.data['paths']['/api/services/{id}/']
        assert 'patch' in detail
        assert 'put' not in detail
        assert 'delete' not in detail


class ServiceUpdateTests(ServiceAccessTestCase):
    def setUp(self):
        super().setUp()
        add_availability(self.walker, self.start.date())
        self.new_start = self.start + ONE_HOUR

    def patch(self, user, payload, service=None):
        self.auth(user)
        return self.client.patch(detail_url(service or self.service), payload, format='json')

    def patch_start(self, user, new_start=None):
        return self.patch(user, {'start_datetime': (new_start or self.new_start).isoformat()})

    def assert_unchanged(self):
        original = (self.service.start_datetime, self.service.end_datetime, self.service.price, self.service.status)
        self.service.refresh_from_db()
        assert (
            self.service.start_datetime,
            self.service.end_datetime,
            self.service.price,
            self.service.status,
        ) == original

    def test_patch_pelo_tutor_em_analise_recalcula_fim_e_preco(self):
        Service.objects.filter(pk=self.service.pk).update(
            end_datetime=self.start + timedelta(minutes=30), price=Decimal('10.00')
        )

        response = self.patch_start(self.tutor_user)

        assert response.status_code == status.HTTP_200_OK
        self.service.refresh_from_db()
        assert self.service.start_datetime == self.new_start
        assert self.service.end_datetime == self.new_start + timedelta(minutes=60)
        assert self.service.price == Decimal('60.00')
        assert Decimal(response.data['price']) == Decimal('60.00')

    def test_patch_troca_os_pets_sem_mexer_no_horario(self):
        other_pet = make_pet(self.tutor, name='Rex')
        Service.objects.filter(pk=self.service.pk).update(price=Decimal('10.00'))

        response = self.patch(self.tutor_user, {'pets': [other_pet.pk]})

        assert response.status_code == status.HTTP_200_OK
        self.service.refresh_from_db()
        assert list(self.service.pets.all()) == [other_pet]
        assert self.service.start_datetime == self.start
        assert self.service.price == Decimal('10.00')

    def test_patch_nao_altera_provider(self):
        other_walker = make_provider(make_user('other-walker@test.com'))

        response = self.patch(
            self.tutor_user,
            {'provider': other_walker.pk, 'start_datetime': self.new_start.isoformat()},
        )

        assert response.status_code == status.HTTP_200_OK
        self.service.refresh_from_db()
        assert self.service.provider == self.walker
        assert self.service.start_datetime == self.new_start

    def test_patch_ignora_status_preco_cliente_e_fim(self):
        other_client = make_client(make_user('other@test.com'))

        response = self.patch(
            self.tutor_user,
            {
                'status': Service.Status.CONFIRMED,
                'price': '1.00',
                'client': other_client.pk,
                'end_datetime': (self.start + timedelta(hours=5)).isoformat(),
                'start_datetime': self.new_start.isoformat(),
            },
        )

        assert response.status_code == status.HTTP_200_OK
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.IN_REVIEW
        assert self.service.price == Decimal('60.00')
        assert self.service.client == self.tutor
        assert self.service.end_datetime == self.new_start + timedelta(minutes=60)

    def test_patch_pelo_passeador_da_403(self):
        response = self.patch_start(self.walker_user)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        self.assert_unchanged()

    def test_patch_por_nao_participante_da_404(self):
        response = self.patch_start(self.outsider_user)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        self.assert_unchanged()

    def test_patch_sem_login_da_401(self):
        response = self.client.patch(detail_url(self.service), {'start_datetime': self.new_start.isoformat()})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patch_fora_de_em_analise_da_409(self):
        for other_status in (
            Service.Status.CONFIRMED,
            Service.Status.IN_PROGRESS,
            Service.Status.COMPLETED,
            Service.Status.CANCELLED,
            Service.Status.REJECTED,
        ):
            with self.subTest(status=other_status):
                self.set_status(other_status)

                response = self.patch_start(self.tutor_user)

                assert response.status_code == status.HTTP_409_CONFLICT
                self.assert_unchanged()

    def test_patch_403_e_409_vem_antes_da_validacao_do_corpo(self):
        forbidden = self.patch(self.walker_user, {'pets': []})
        self.set_status(Service.Status.CONFIRMED)
        conflict = self.patch(self.tutor_user, {'pets': []})

        assert forbidden.status_code == status.HTTP_403_FORBIDDEN
        assert conflict.status_code == status.HTTP_409_CONFLICT

    def test_patch_revalida_o_status_dentro_da_transacao(self):
        serializer_class = service_serializers.ServiceUpdateSerializer
        validate = serializer_class.validate

        def confirmed_in_the_meantime(serializer, data):
            Service.objects.filter(pk=self.service.pk).update(status=Service.Status.CONFIRMED)
            return validate(serializer, data)

        with mock.patch.object(serializer_class, 'validate', autospec=True, side_effect=confirmed_in_the_meantime):
            response = self.patch_start(self.tutor_user)

        assert response.status_code == status.HTTP_409_CONFLICT
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.CONFIRMED
        assert self.service.start_datetime == self.start

    def test_patch_com_conflito_da_409(self):
        other_client = make_client(make_user('other@test.com'))
        make_service(other_client, self.walker, status=Service.Status.CONFIRMED, start=self.new_start)

        response = self.patch_start(self.tutor_user)

        assert response.status_code == status.HTTP_409_CONFLICT
        self.assert_unchanged()

    def test_patch_para_horario_que_sobrepoe_o_proprio_servico_da_200(self):
        response = self.patch_start(self.tutor_user, self.start + timedelta(minutes=30))

        assert response.status_code == status.HTTP_200_OK

    def test_patch_no_passado_da_400(self):
        past = self.start - timedelta(days=30)
        add_availability(self.walker, past.date())

        response = self.patch_start(self.tutor_user, past)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.assert_unchanged()

    def test_patch_fora_da_disponibilidade_da_400(self):
        next_day = self.start + timedelta(days=1)

        response = self.patch_start(self.tutor_user, next_day)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        self.assert_unchanged()

    def test_patch_com_pet_de_outro_tutor_da_400(self):
        other_client = make_client(make_user('other@test.com'))
        foreign_pet = make_pet(other_client, name='Alheio')

        response = self.patch(self.tutor_user, {'pets': [foreign_pet.pk]})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert list(self.service.pets.all()) == [self.pet]

    def test_patch_sem_pets_da_400(self):
        response = self.patch(self.tutor_user, {'pets': []})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'pets' in response.data
        assert list(self.service.pets.all()) == [self.pet]


class ServiceContactPhoneTests(ServiceAccessTestCase):
    def phone_for(self, user):
        self.auth(user)
        response = self.client.get(detail_url(self.service))
        assert response.status_code == status.HTTP_200_OK
        return response.data['contact_phone']

    def test_contact_phone_visivel_so_em_2_e_3(self):
        hidden = (
            Service.Status.IN_REVIEW,
            Service.Status.COMPLETED,
            Service.Status.CANCELLED,
            Service.Status.REJECTED,
        )
        for hidden_status in hidden:
            with self.subTest(status=hidden_status):
                self.set_status(hidden_status)

                assert self.phone_for(self.tutor_user) is None
                assert self.phone_for(self.walker_user) is None
        for visible_status in (Service.Status.CONFIRMED, Service.Status.IN_PROGRESS):
            with self.subTest(status=visible_status):
                self.set_status(visible_status)

                assert self.phone_for(self.tutor_user) == WALKER_PHONE
                assert self.phone_for(self.walker_user) == TUTOR_PHONE

    def test_contact_phone_na_lista_segue_a_mesma_regra(self):
        self.set_status(Service.Status.CONFIRMED)

        (tutor_item,) = self.results(self.tutor_user)
        (walker_item,) = self.results(self.walker_user)

        assert tutor_item['contact_phone'] == WALKER_PHONE
        assert walker_item['contact_phone'] == TUTOR_PHONE

    def test_contact_phone_sem_telefone_cadastrado_e_nulo(self):
        self.set_status(Service.Status.CONFIRMED)
        self.walker_user.phone = None
        self.walker_user.save(update_fields=['phone'])

        assert self.phone_for(self.tutor_user) is None

    def test_contact_phone_vem_nas_respostas_das_acoes(self):
        add_availability(self.walker, self.start.date())
        self.auth(self.walker_user)

        response = self.client.post(self.action_url(self.service, 'confirm'))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['contact_phone'] == TUTOR_PHONE


class ServiceSerializerFieldsTests(ServiceAccessTestCase):
    def retrieve(self):
        self.auth(self.tutor_user)
        response = self.client.get(detail_url(self.service))
        assert response.status_code == status.HTTP_200_OK
        return response.data

    def test_expoe_finished_at(self):
        finished = self.start + timedelta(minutes=40)
        Service.objects.filter(pk=self.service.pk).update(finished_at=finished)

        assert self.retrieve()['finished_at'] is not None

    def test_duration_usa_inicio_e_fim_reais(self):
        started = self.start + timedelta(minutes=5)
        Service.objects.filter(pk=self.service.pk).update(
            started_at=started, finished_at=started + timedelta(hours=1, minutes=30, seconds=5)
        )

        assert self.retrieve()['duration'] == '01:30:05'

    def test_duration_nula_enquanto_o_passeio_nao_termina(self):
        Service.objects.filter(pk=self.service.pk).update(started_at=self.start)

        assert self.retrieve()['duration'] is None

    def test_distance_le_distance_meters(self):
        assert self.retrieve()['distance'] is None
        Service.objects.filter(pk=self.service.pk).update(distance_meters=SAVED_DISTANCE)

        assert self.retrieve()['distance'] == ROUNDED_DISTANCE


class ServiceListQueryCountTests(ServiceAccessTestCase):
    def add_service_with_pictures(self, index):
        walker_user = make_user(f'walker{index}@test.com', full_name=f'Passeador {index}', phone='47999990009')
        walker_user.profile_picture = make_picture(f'walker{index}')
        walker_user.save(update_fields=['profile_picture'])
        pet = make_pet(self.tutor, name=f'Pet {index}')
        pet.pet_picture = make_picture(f'pet{index}')
        pet.save(update_fields=['pet_picture'])
        return make_service(self.tutor, make_provider(walker_user), status=Service.Status.CONFIRMED, pets=[pet])

    def test_lista_de_servicos_nao_faz_n_mais_1(self):
        self.tutor_user.profile_picture = make_picture('tutor')
        self.tutor_user.save(update_fields=['profile_picture'])
        self.pet.pet_picture = make_picture('pet')
        self.pet.save(update_fields=['pet_picture'])
        self.auth(self.tutor_user)

        with CaptureQueriesContext(connection) as single:
            first = self.client.get(list_url())
        assert len(first.data['results']) == 1

        for index in range(SERVICES_PER_LIST - 1):
            self.add_service_with_pictures(index)
        with self.assertNumQueries(len(single)):
            response = self.client.get(list_url())

        results = response.data['results']
        assert len(results) == SERVICES_PER_LIST
        assert all(item['provider_picture'] for item in results[:-1])
        assert all(item['pets'][0]['pet_picture'] for item in results)
        assert all(item['client_picture'] for item in results)
