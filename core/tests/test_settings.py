import os
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from app.env import DEFAULT_ALLOWED_HOSTS, env_bool, env_list

PRODUCTION_HOST = 'doggo-backend.class.fabricadesoftware.ifc.edu.br'


class EnvBoolTests(SimpleTestCase):
    def test_env_bool_interpreta_false_como_falso(self):
        for valor in ('False', 'false', '0', 'no', ''):
            with self.subTest(valor=valor), mock.patch.dict(os.environ, {'FLAG_TESTE': valor}):
                assert env_bool('FLAG_TESTE', True) is False

    def test_env_bool_interpreta_true(self):
        for valor in ('True', 'true', '1', 'yes'):
            with self.subTest(valor=valor), mock.patch.dict(os.environ, {'FLAG_TESTE': valor}):
                assert env_bool('FLAG_TESTE', False) is True

    def test_env_bool_usa_padrao_quando_ausente(self):
        with mock.patch.dict(os.environ):
            os.environ.pop('FLAG_TESTE', None)
            assert env_bool('FLAG_TESTE', True) is True
            assert env_bool('FLAG_TESTE', False) is False


class EnvListTests(SimpleTestCase):
    def test_env_list_separa_por_virgula_e_remove_espacos(self):
        with mock.patch.dict(os.environ, {'LISTA_TESTE': 'a.com, b.com ,,c.com'}):
            assert env_list('LISTA_TESTE', ['x']) == ['a.com', 'b.com', 'c.com']

    def test_env_list_usa_padrao_quando_ausente(self):
        with mock.patch.dict(os.environ):
            os.environ.pop('LISTA_TESTE', None)
            assert env_list('LISTA_TESTE', ['x', 'y']) == ['x', 'y']


class SettingsTests(SimpleTestCase):
    def test_settings_nao_libera_todas_as_origens(self):
        assert not getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False)

    def test_allowed_hosts_padrao_inclui_dominio_de_producao(self):
        with mock.patch.dict(os.environ):
            os.environ.pop('ALLOWED_HOSTS', None)
            assert PRODUCTION_HOST in env_list('ALLOWED_HOSTS', DEFAULT_ALLOWED_HOSTS)
