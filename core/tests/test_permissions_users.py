from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.throttling import ScopedRateThrottle

from core.tests.helpers import FlowTestCase
from core.validators.cpf import cpf_validator, is_valid_cpf

User = get_user_model()

VALID_CPF = '52998224725'
MASKED_VALID_CPF = '529.982.247-25'
STRONG_PASSWORD = 'Cachorro-Feliz-93'
LOGIN_PASSWORD = 'pw12345'
THROTTLE_LIMIT = 2


def users_list_url():
    return reverse('users-list')


def user_detail_url(user):
    return reverse('users-detail', args=[user.pk])


def registration_payload(**overrides):
    payload = {
        'email': 'novo@test.com',
        'cpf': VALID_CPF,
        'phone': '47999990003',
        'full_name': 'Novo Usuário',
        'password': STRONG_PASSWORD,
    }
    payload.update(overrides)
    return payload


class IsValidCpfTestCase(SimpleTestCase):
    def test_aceita_cpf_valido(self):
        assert is_valid_cpf(VALID_CPF) is True

    def test_rejeita_digitos_todos_iguais(self):
        assert is_valid_cpf('11111111111') is False

    def test_rejeita_digito_verificador_errado(self):
        assert is_valid_cpf('12345678900') is False

    def test_rejeita_tamanho_errado(self):
        assert is_valid_cpf(VALID_CPF[:-1]) is False
        assert is_valid_cpf(VALID_CPF + '0') is False

    def test_rejeita_caracteres_nao_numericos(self):
        assert is_valid_cpf(MASKED_VALID_CPF) is False
        assert is_valid_cpf('5299822472a') is False

    def test_cpf_validator_mantem_mensagens(self):
        assert cpf_validator(VALID_CPF) == f'O cpf {VALID_CPF} é válido'
        assert cpf_validator('11111111111') == 'O cpf 11111111111 não é válido'


class UserAccessTestCase(FlowTestCase):
    def test_lista_de_usuarios_mostra_so_o_proprio(self):
        self.auth(self.tutor_user)

        response = self.client.get(users_list_url())

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['results']] == [self.tutor_user.pk]

    def test_nao_ve_outro_usuario(self):
        self.auth(self.tutor_user)

        response = self.client.get(user_detail_url(self.walker_user))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_nao_edita_outro_usuario(self):
        self.auth(self.tutor_user)

        response = self.client.patch(user_detail_url(self.walker_user), {'full_name': 'Invadido'})

        assert response.status_code == status.HTTP_404_NOT_FOUND
        self.walker_user.refresh_from_db()
        assert self.walker_user.full_name == 'Passeador'

    def test_nao_apaga_outro_usuario(self):
        self.auth(self.tutor_user)

        response = self.client.delete(user_detail_url(self.walker_user))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert User.objects.filter(pk=self.walker_user.pk).exists()

    def test_nao_se_promove_a_admin(self):
        self.auth(self.tutor_user)

        response = self.client.patch(user_detail_url(self.tutor_user), {'is_staff': True, 'is_superuser': True})

        assert response.status_code == status.HTTP_200_OK
        self.tutor_user.refresh_from_db()
        assert self.tutor_user.is_staff is False
        assert self.tutor_user.is_superuser is False

    def test_nao_troca_email_nem_cpf_proprios(self):
        self.auth(self.tutor_user)
        old_email = self.tutor_user.email
        old_cpf = self.tutor_user.cpf

        response = self.client.patch(user_detail_url(self.tutor_user), {'email': 'outro@test.com', 'cpf': VALID_CPF})

        assert response.status_code == status.HTTP_200_OK
        self.tutor_user.refresh_from_db()
        assert self.tutor_user.email == old_email
        assert self.tutor_user.cpf == old_cpf

    def test_edita_nome_e_telefone_proprios(self):
        self.auth(self.tutor_user)

        response = self.client.patch(
            user_detail_url(self.tutor_user), {'full_name': 'Tutor Novo', 'phone': '47988887777'}
        )

        assert response.status_code == status.HTTP_200_OK
        self.tutor_user.refresh_from_db()
        assert self.tutor_user.full_name == 'Tutor Novo'
        assert self.tutor_user.phone == '47988887777'

    def test_post_em_users_retorna_405(self):
        self.auth(self.tutor_user)

        response = self.client.post(users_list_url(), registration_payload())

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_put_em_users_retorna_405(self):
        self.auth(self.tutor_user)

        response = self.client.put(user_detail_url(self.tutor_user), {'full_name': 'Tutor Novo'})

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_me_retorna_o_proprio_usuario(self):
        self.auth(self.tutor_user)

        response = self.client.get(reverse('users-me'))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == self.tutor_user.pk

    def test_profile_mantem_formato(self):
        self.auth(self.tutor_user)

        response = self.client.get(reverse('user_profile'))

        assert response.status_code == status.HTTP_200_OK
        assert 'provider_profile' in response.data
        assert 'client_profile' in response.data


class UserRegistrationTestCase(FlowTestCase):
    def register(self, **overrides):
        return self.client.post(reverse('user_registration'), registration_payload(**overrides))

    def test_cadastro_rejeita_cpf_invalido(self):
        for cpf in ('11111111111', '12345678900'):
            with self.subTest(cpf=cpf):
                response = self.register(cpf=cpf)

                assert response.status_code == status.HTTP_400_BAD_REQUEST
                assert response.data['cpf'][0] == 'CPF inválido.'
        assert not User.objects.filter(email='novo@test.com').exists()

    def test_cadastro_aceita_cpf_com_mascara(self):
        response = self.register(cpf=MASKED_VALID_CPF)

        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.get(email='novo@test.com').cpf == VALID_CPF

    def test_cadastro_rejeita_senha_fraca(self):
        response = self.register(password='12345678')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'password' in response.data
        assert not User.objects.filter(email='novo@test.com').exists()

    def test_cadastro_com_dados_validos(self):
        response = self.register()

        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.get(email='novo@test.com').check_password(STRONG_PASSWORD)
        assert 'password' not in response.data


class AuthThrottleTestCase(FlowTestCase):
    def test_login_bloqueado_apos_limite(self):
        credentials = {'email': self.tutor_user.email, 'password': LOGIN_PASSWORD}

        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'auth': f'{THROTTLE_LIMIT}/min'}):
            statuses = [self.client.post(reverse('token_obtain_pair'), credentials).status_code for _ in range(3)]

        assert statuses == [status.HTTP_200_OK, status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS]

    def test_cadastro_bloqueado_apos_limite(self):
        with mock.patch.dict(ScopedRateThrottle.THROTTLE_RATES, {'auth': f'{THROTTLE_LIMIT}/min'}):
            statuses = [
                self.client.post(reverse('user_registration'), registration_payload(email=f'novo{n}@test.com'))
                for n in range(3)
            ]

        assert [response.status_code for response in statuses] == [
            status.HTTP_201_CREATED,
            status.HTTP_201_CREATED,
            status.HTTP_429_TOO_MANY_REQUESTS,
        ]
