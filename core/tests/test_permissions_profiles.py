from decimal import Decimal

from django.urls import reverse
from rest_framework import status

from core.models import ClientProfile, ProviderProfile, Review
from core.tests.helpers import FlowTestCase, make_client, make_provider, make_user
from uploader.models import Image

CLIENT_DUPLICATE_MESSAGE = 'Usuário já possui perfil de cliente.'
PROVIDER_DUPLICATE_MESSAGE = 'Usuário já possui perfil de prestador.'
PROFILE_DELETE_BLOCKED_MESSAGE = 'Não é possível excluir o perfil: há passeios ou avaliações vinculados.'
VALID_CPF = '52998224725'
PRIVATE_PROVIDER_KEYS = ('email', 'phone', 'services', 'user')
EXTRA_PROVIDERS = 4
REVIEW_COUNT = 2
AVERAGE_OF_5_AND_3 = 4.0
AVERAGE_OF_5_AND_4 = 4.5
FAR_LATITUDE = Decimal('10.000000')
FAR_LONGITUDE = Decimal('10.000000')
MAX_DISTANCE_KM = 10


def clients_list_url():
    return reverse('clients-list')


def client_detail_url(client):
    return reverse('clients-detail', args=[client.pk])


def providers_list_url():
    return reverse('providers-list')


def provider_detail_url(provider):
    return reverse('providers-detail', args=[provider.pk])


def search_url():
    return reverse('search')


def provider_payload(service_type, **overrides):
    payload = {
        'fixed_latitude': '-27.500000',
        'fixed_longitude': '-48.500000',
        'service_type': service_type.pk,
        'price_per_hour': '50.00',
        'is_active': True,
    }
    payload.update(overrides)
    return payload


def make_review(provider, client, rating):
    return Review.objects.create(provider=provider, client=client, rating=rating, comment='ok')


class ClientProfileAccessTestCase(FlowTestCase):
    def test_lista_de_clientes_mostra_so_o_proprio(self):
        other = make_client(self.outsider_user)
        self.auth(self.tutor_user)

        response = self.client.get(clients_list_url())

        assert response.status_code == status.HTTP_200_OK
        ids = [item['id'] for item in response.data['results']]
        assert ids == [self.tutor.pk]
        assert other.pk not in ids

    def test_nao_edita_cliente_alheio(self):
        other = make_client(self.outsider_user)
        self.auth(self.tutor_user)

        response = self.client.patch(client_detail_url(other), {'last_latitude': '10.000000'})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        other.refresh_from_db()
        assert other.last_latitude is None

    def test_nao_remove_cliente_alheio(self):
        other = make_client(self.outsider_user)
        self.auth(self.tutor_user)

        response = self.client.delete(client_detail_url(other))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert ClientProfile.objects.filter(pk=other.pk).exists()

    def test_nao_ve_detalhe_de_cliente_alheio(self):
        self.auth(self.walker_user)

        response = self.client.get(client_detail_url(self.tutor))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_dono_edita_o_proprio_cliente(self):
        self.auth(self.tutor_user)

        response = self.client.patch(client_detail_url(self.tutor), {'last_latitude': '10.000000'})

        assert response.status_code == status.HTTP_200_OK
        self.tutor.refresh_from_db()
        assert self.tutor.last_latitude == Decimal('10.000000')

    def test_cria_perfil_de_cliente_para_si(self):
        self.auth(self.outsider_user)

        response = self.client.post(clients_list_url(), {})

        assert response.status_code == status.HTTP_201_CREATED
        assert ClientProfile.objects.get(user=self.outsider_user).pk == response.data['id']

    def test_nao_cria_segundo_perfil_de_cliente(self):
        self.auth(self.tutor_user)

        response = self.client.post(clients_list_url(), {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert CLIENT_DUPLICATE_MESSAGE in response.data['non_field_errors']
        assert ClientProfile.objects.filter(user=self.tutor_user).count() == 1

    def test_detalhe_do_proprio_cliente_nao_expoe_credenciais(self):
        self.tutor_user.cpf = VALID_CPF
        self.tutor_user.save()
        self.auth(self.tutor_user)

        response = self.client.get(client_detail_url(self.tutor))

        body = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        for private in ('password', 'cpf', VALID_CPF, self.tutor_user.password, self.tutor_user.phone):
            assert private not in body
        assert 'password' not in response.data['user']
        assert response.data['user']['id'] == self.tutor_user.pk
        assert [pet['id'] for pet in response.data['pets']] == [self.pet.pk]

    def test_exclui_o_proprio_cliente_sem_historico(self):
        own = make_client(self.outsider_user)
        self.auth(self.outsider_user)

        response = self.client.delete(client_detail_url(own))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ClientProfile.objects.filter(pk=own.pk).exists()

    def test_nao_exclui_cliente_com_passeios(self):
        self.auth(self.tutor_user)

        response = self.client.delete(client_detail_url(self.tutor))

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data['detail'] == PROFILE_DELETE_BLOCKED_MESSAGE
        assert ClientProfile.objects.filter(pk=self.tutor.pk).exists()


class ProviderProfileAccessTestCase(FlowTestCase):
    def test_qualquer_logado_ve_prestadores(self):
        self.auth(self.outsider_user)

        response = self.client.get(providers_list_url())

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['results']] == [self.walker.pk]

    def test_nao_edita_prestador_alheio(self):
        self.auth(self.outsider_user)

        patch_response = self.client.patch(provider_detail_url(self.walker), {'price_per_hour': '1.00'})
        delete_response = self.client.delete(provider_detail_url(self.walker))

        assert patch_response.status_code == status.HTTP_403_FORBIDDEN
        assert delete_response.status_code == status.HTTP_403_FORBIDDEN
        self.walker.refresh_from_db()
        assert self.walker.price_per_hour == Decimal('60.00')

    def test_dono_altera_presenca(self):
        self.auth(self.walker_user)

        response = self.client.patch(provider_detail_url(self.walker), {'is_active': False})

        assert response.status_code == status.HTTP_200_OK
        self.walker.refresh_from_db()
        assert self.walker.is_active is False

    def test_exclui_o_proprio_prestador_sem_historico(self):
        own = make_provider(self.outsider_user, service_type=self.walker.service_type)
        self.auth(self.outsider_user)

        response = self.client.delete(provider_detail_url(own))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ProviderProfile.objects.filter(pk=own.pk).exists()

    def test_nao_exclui_prestador_com_passeios(self):
        self.auth(self.walker_user)

        response = self.client.delete(provider_detail_url(self.walker))

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.data['detail'] == PROFILE_DELETE_BLOCKED_MESSAGE
        assert ProviderProfile.objects.filter(pk=self.walker.pk).exists()

    def test_nao_exclui_prestador_com_avaliacoes(self):
        own = make_provider(self.outsider_user, service_type=self.walker.service_type)
        make_review(own, self.tutor, 5)
        self.auth(self.outsider_user)

        response = self.client.delete(provider_detail_url(own))

        assert response.status_code == status.HTTP_409_CONFLICT
        assert ProviderProfile.objects.filter(pk=own.pk).exists()

    def test_cria_perfil_de_prestador_para_si(self):
        self.auth(self.outsider_user)

        response = self.client.post(providers_list_url(), provider_payload(self.walker.service_type))

        assert response.status_code == status.HTTP_201_CREATED
        created = ProviderProfile.objects.get(user=self.outsider_user)
        assert created.is_active is True

    def test_nao_cria_segundo_perfil_de_prestador(self):
        self.auth(self.walker_user)

        response = self.client.post(providers_list_url(), provider_payload(self.walker.service_type))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert PROVIDER_DUPLICATE_MESSAGE in response.data['non_field_errors']
        assert ProviderProfile.objects.filter(user=self.walker_user).count() == 1

    def test_detalhe_publico_nao_expoe_contato(self):
        self.auth(self.outsider_user)

        response = self.client.get(provider_detail_url(self.walker))

        assert response.status_code == status.HTTP_200_OK
        for key in PRIVATE_PROVIDER_KEYS:
            assert key not in response.data
        assert response.data['full_name'] == self.walker_user.full_name

    def test_classification_e_rating_count(self):
        make_review(self.walker, self.tutor, 5)
        make_review(self.walker, self.tutor, 3)
        self.auth(self.outsider_user)

        list_response = self.client.get(providers_list_url())
        detail_response = self.client.get(provider_detail_url(self.walker))

        listed = list_response.data['results'][0]
        assert listed['classification'] == AVERAGE_OF_5_AND_3
        assert listed['rating_count'] == REVIEW_COUNT
        assert detail_response.data['classification'] == AVERAGE_OF_5_AND_3
        assert detail_response.data['rating_count'] == REVIEW_COUNT

    def test_prestador_sem_avaliacao_tem_classificacao_nula(self):
        self.auth(self.outsider_user)

        response = self.client.get(providers_list_url())

        listed = response.data['results'][0]
        assert listed['classification'] is None
        assert listed['rating_count'] == 0

    def test_lista_de_prestadores_sem_n_mais_1(self):
        self.walker_user.profile_picture = Image.objects.create(file='images/walker.png')
        self.walker_user.save()
        self.auth(self.outsider_user)

        with self.assertNumQueries(2):  # contagem da paginação + listagem
            self.client.get(providers_list_url())

        for index in range(EXTRA_PROVIDERS):
            user = make_user(f'extra{index}@test.com', full_name=f'Extra {index}')
            user.profile_picture = Image.objects.create(file=f'images/extra{index}.png')
            user.save()
            provider = make_provider(user, service_type=self.walker.service_type)
            make_review(provider, self.tutor, 4)

        with self.assertNumQueries(2):
            response = self.client.get(providers_list_url())

        assert len(response.data['results']) == EXTRA_PROVIDERS + 1

    def test_filtros_da_lista_continuam_valendo_com_avaliacoes(self):
        make_review(self.walker, self.tutor, 5)
        make_review(self.walker, self.tutor, 3)
        far_user = make_user('far@test.com', full_name='Longe')
        far = make_provider(far_user, service_type=self.walker.service_type)
        far.fixed_latitude = FAR_LATITUDE
        far.fixed_longitude = FAR_LONGITUDE
        far.is_active = False
        far.save()
        self.auth(self.outsider_user)

        near_params = {
            'lat': str(self.walker.fixed_latitude),
            'lon': str(self.walker.fixed_longitude),
            'max_distance': str(MAX_DISTANCE_KM),
        }

        near_response = self.client.get(providers_list_url(), near_params)
        inactive_response = self.client.get(providers_list_url(), {'is_active': 'false'})

        assert [item['id'] for item in near_response.data['results']] == [self.walker.pk]
        near = near_response.data['results'][0]
        assert near['distance'] <= MAX_DISTANCE_KM
        assert near['classification'] == AVERAGE_OF_5_AND_3
        assert near['rating_count'] == REVIEW_COUNT
        assert [item['id'] for item in inactive_response.data['results']] == [far.pk]


class SearchPrivacyTestCase(FlowTestCase):
    def setUp(self):
        super().setUp()
        self.tutor.last_latitude = Decimal('-27.123456')
        self.tutor.last_longitude = Decimal('-48.654321')
        self.tutor.save()
        self.auth(self.outsider_user)

    def test_busca_nao_retorna_clientes(self):
        response = self.client.get(search_url(), {'q': self.tutor_user.full_name})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['clients'] == []

    def test_busca_nao_expoe_coordenadas_de_cliente(self):
        response = self.client.get(search_url(), {'q': self.tutor_user.full_name})

        assert 'last_latitude' not in response.content.decode()
        assert '-27.123456' not in response.content.decode()

    def test_busca_devolve_prestadores_com_classificacao(self):
        make_review(self.walker, self.tutor, 5)
        make_review(self.walker, self.tutor, 4)

        response = self.client.get(search_url(), {'q': self.walker_user.full_name})

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['providers']] == [self.walker.pk]
        found = response.data['providers'][0]
        assert found['classification'] == AVERAGE_OF_5_AND_4
        assert found['rating_count'] == REVIEW_COUNT

    def test_busca_sem_termo_devolve_listas_vazias(self):
        response = self.client.get(search_url())

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {'providers': [], 'clients': []}
