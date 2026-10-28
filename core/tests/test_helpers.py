from datetime import time

from asgiref.sync import async_to_sync
from django.core.cache import cache
from django.test import SimpleTestCase
from django.utils import timezone

from core.models import Service
from core.tests.helpers import FakeRedis, FlowTestCase, add_availability, make_pet, make_service, raises


class RaisesTests(SimpleTestCase):
    def test_captura_a_excecao_esperada(self):
        with raises(ValueError) as erro:
            raise ValueError('boom')

        assert str(erro.exception) == 'boom'

    def test_falha_quando_nada_e_levantado(self):
        falhou = False
        try:
            with raises(ValueError):
                pass
        except AssertionError:
            falhou = True

        assert falhou

    def test_nao_engole_outra_excecao(self):
        propagou = False
        try:
            with raises(ValueError):
                raise KeyError('x')
        except KeyError:
            propagou = True

        assert propagou


class FakeRedisTests(FlowTestCase):
    def test_get_devolve_none_quando_ausente(self):
        redis = FakeRedis()

        assert async_to_sync(redis.get)('x') is None

    def test_set_e_get_devolvem_bytes_como_o_redis_py(self):
        redis = FakeRedis()

        async_to_sync(redis.set)('x', 'valor', ex=30)

        assert async_to_sync(redis.get)('x') == b'valor'

    def test_set_preserva_bytes(self):
        redis = FakeRedis()

        async_to_sync(redis.set)('x', b'\x00\x01')

        assert async_to_sync(redis.get)('x') == b'\x00\x01'

    def test_delete_remove_varias_chaves(self):
        redis = FakeRedis()
        async_to_sync(redis.set)('a', '1')
        async_to_sync(redis.set)('b', '2')

        async_to_sync(redis.delete)('a', 'b', 'inexistente')

        assert async_to_sync(redis.get)('a') is None
        assert async_to_sync(redis.get)('b') is None

    def test_aclose_nao_levanta_erro(self):
        async_to_sync(FakeRedis().aclose)()


class FlowTestCaseTests(FlowTestCase):
    def test_setup_cria_atores_e_servico(self):
        assert self.tutor_user.phone == '47999990001'
        assert self.tutor.user == self.tutor_user
        assert self.walker_user.phone == '47999990002'
        assert self.walker.user == self.walker_user
        assert self.walker.is_active is True
        assert not hasattr(self.outsider_user, 'client_profile')
        assert not hasattr(self.outsider_user, 'provider_profile')
        assert self.pet.owner == self.tutor
        assert self.service.status == Service.Status.IN_REVIEW
        assert self.service.client == self.tutor
        assert self.service.provider == self.walker
        assert list(self.service.pets.all()) == [self.pet]

    def test_action_url_aponta_para_a_acao_do_servico(self):
        assert self.action_url(self.service, 'detail') == f'/api/services/{self.service.pk}/'

    def test_auth_autentica_o_cliente_de_teste(self):
        self.auth(self.tutor_user)

        assert self.client.handler._force_user == self.tutor_user


class FlowTestCaseCacheTests(FlowTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cache.set('chave-de-teste', 1)

    def test_setup_limpa_o_cache(self):
        assert cache.get('chave-de-teste') is None


class FactoryTests(FlowTestCase):
    def test_make_service_usa_padroes_do_contrato(self):
        service = make_service(self.tutor, self.walker)

        assert service.status == Service.Status.IN_REVIEW
        assert service.end_datetime - service.start_datetime == timezone.timedelta(minutes=60)
        assert service.start_datetime > timezone.now()
        assert service.price == self.walker.price_per_hour
        assert service.service_type == self.walker.service_type
        assert service.pets.count() == 1

    def test_make_service_aceita_pets_informados(self):
        outro_pet = make_pet(self.tutor, name='Rex')

        service = make_service(self.tutor, self.walker, pets=[self.pet, outro_pet])

        assert set(service.pets.all()) == {self.pet, outro_pet}

    def test_add_availability_cobre_o_dia_inteiro_por_padrao(self):
        on_date = timezone.localdate()

        availability = add_availability(self.walker, on_date)

        assert availability.weekday == on_date.weekday()
        assert availability.start_time == time(0, 0)
        assert availability.end_time == time(23, 59)
        assert availability.provider == self.walker
