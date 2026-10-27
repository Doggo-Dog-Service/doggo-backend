from types import SimpleNamespace
from unittest import mock

from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import AccessToken

from core.middleware import JWTAuthMiddlewareStack
from core.models import Service, ServiceLocation
from core.routing import websocket_urlpatterns
from core.services import redis_service
from core.tests.helpers import FakeRedis, make_client, make_provider, make_service, make_user

RECEIVE_TIMEOUT = 2
CLOSE_UNAUTHENTICATED = 4001
CLOSE_NOT_PARTICIPANT = 4003
CLOSE_SERVICE_NOT_FOUND = 4004
IN_MEMORY_LAYER = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
NOT_IN_PROGRESS_MESSAGE = 'Localização só é aceita com o passeio em andamento.'
LOCATION = {'type': 'location', 'latitude': -27.5, 'longitude': -48.5}


def build_scenario(status):
    """Tutor, passeador, um estranho e o serviço no `status` dado (síncrono: roda via `database_sync_to_async`)."""
    tutor_user = make_user('tutor@test.com', full_name='Tutor', phone='47999990001')
    walker_user = make_user('walker@test.com', full_name='Passeador', phone='47999990002')
    outsider_user = make_user('outsider@test.com', full_name='Estranho')
    service = make_service(make_client(tutor_user), make_provider(walker_user), status=status)
    return SimpleNamespace(service_id=service.pk, tutor=tutor_user, walker=walker_user, outsider=outsider_user)


def token_for(user):
    return str(AccessToken.for_user(user))


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYER)
class ServiceConsumerTests(TransactionTestCase):
    """O WebSocket do passeio só aceita localização do passeador com o passeio em andamento."""

    def setUp(self):
        self.redis = FakeRedis()
        patcher = mock.patch('core.consumers.service_location.get_shared_redis', return_value=self.redis)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.application = JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns))

    async def scenario(self, status):
        return await database_sync_to_async(build_scenario)(status)

    def communicator(self, service_id, user=None):
        query = f'?token={token_for(user)}' if user is not None else ''
        return WebsocketCommunicator(self.application, f'/ws/services/{service_id}/{query}')

    async def connect(self, service_id, user):
        communicator = self.communicator(service_id, user)
        connected, _ = await communicator.connect()
        assert connected
        return communicator

    async def receive(self, communicator):
        return await communicator.receive_json_from(timeout=RECEIVE_TIMEOUT)

    async def send_event(self, service_id, event_type, status):
        await get_channel_layer().group_send(
            f'service_{service_id}',
            {'type': 'service_event', 'event_type': event_type, 'service_id': service_id, 'status': status},
        )

    async def test_sem_token_fecha_com_4001(self):
        scenario = await self.scenario(Service.Status.IN_PROGRESS)
        communicator = self.communicator(scenario.service_id)

        connected, code = await communicator.connect()

        assert not connected
        assert code == CLOSE_UNAUTHENTICATED
        await communicator.disconnect()

    async def test_nao_participante_fecha_com_4003(self):
        scenario = await self.scenario(Service.Status.IN_PROGRESS)
        communicator = self.communicator(scenario.service_id, scenario.outsider)

        connected, code = await communicator.connect()

        assert not connected
        assert code == CLOSE_NOT_PARTICIPANT
        await communicator.disconnect()

    async def test_servico_inexistente_fecha_com_4004(self):
        scenario = await self.scenario(Service.Status.IN_PROGRESS)
        communicator = self.communicator(scenario.service_id + 1000, scenario.walker)

        connected, code = await communicator.connect()

        assert not connected
        assert code == CLOSE_SERVICE_NOT_FOUND
        await communicator.disconnect()

    async def test_localizacao_recusada_quando_confirmado(self):
        scenario = await self.scenario(Service.Status.CONFIRMED)
        walker = await self.connect(scenario.service_id, scenario.walker)

        await walker.send_json_to(LOCATION)
        reply = await self.receive(walker)

        assert reply == {'type': 'error', 'message': NOT_IN_PROGRESS_MESSAGE}
        assert await walker.receive_nothing()
        assert self.redis.data == {}
        assert not await database_sync_to_async(ServiceLocation.objects.exists)()
        await walker.disconnect()

    async def test_localizacao_aceita_em_andamento(self):
        scenario = await self.scenario(Service.Status.IN_PROGRESS)
        walker = await self.connect(scenario.service_id, scenario.walker)
        tutor = await self.connect(scenario.service_id, scenario.tutor)

        await walker.send_json_to(LOCATION)
        message = await self.receive(tutor)

        assert message['type'] == 'location'
        assert message['location']['latitude'] == LOCATION['latitude']
        assert message['location']['longitude'] == LOCATION['longitude']
        assert message['distance'] == 0.0
        assert await self.receive(walker) == message
        assert await database_sync_to_async(ServiceLocation.objects.count)() == 1
        await walker.disconnect()
        await tutor.disconnect()

    async def test_localizacao_aceita_quando_o_banco_ja_esta_em_andamento(self):
        """O status em memória pode estar velho (início por outra conexão): o consumer relê o banco antes de recusar."""
        scenario = await self.scenario(Service.Status.CONFIRMED)
        walker = await self.connect(scenario.service_id, scenario.walker)
        await database_sync_to_async(Service.objects.filter(pk=scenario.service_id).update)(
            status=Service.Status.IN_PROGRESS
        )

        await walker.send_json_to(LOCATION)
        message = await self.receive(walker)

        assert message['type'] == 'location'
        await walker.disconnect()

    async def test_tutor_nao_envia_localizacao(self):
        scenario = await self.scenario(Service.Status.IN_PROGRESS)
        tutor = await self.connect(scenario.service_id, scenario.tutor)

        await tutor.send_json_to(LOCATION)
        reply = await self.receive(tutor)

        assert reply == {'type': 'error', 'message': 'Apenas o prestador pode enviar localização.'}
        assert self.redis.data == {}
        await tutor.disconnect()

    async def test_evento_de_inicio_libera_localizacao(self):
        scenario = await self.scenario(Service.Status.CONFIRMED)
        walker = await self.connect(scenario.service_id, scenario.walker)

        await walker.send_json_to(LOCATION)
        assert (await self.receive(walker))['message'] == NOT_IN_PROGRESS_MESSAGE

        # O banco segue em "confirmado": só o evento do grupo atualiza o status em memória.
        await self.send_event(scenario.service_id, 'walk_started', Service.Status.IN_PROGRESS)
        event = await self.receive(walker)
        await walker.send_json_to(LOCATION)
        message = await self.receive(walker)

        assert event == {'type': 'walk_started', 'service_id': scenario.service_id, 'status': 3}
        assert message['type'] == 'location'
        await walker.disconnect()

    async def test_evento_de_conclusao_bloqueia_localizacao(self):
        scenario = await self.scenario(Service.Status.IN_PROGRESS)
        walker = await self.connect(scenario.service_id, scenario.walker)
        await database_sync_to_async(Service.objects.filter(pk=scenario.service_id).update)(
            status=Service.Status.COMPLETED
        )

        await self.send_event(scenario.service_id, 'walk_completed', Service.Status.COMPLETED)
        event = await self.receive(walker)
        await walker.send_json_to(LOCATION)
        reply = await self.receive(walker)

        assert event == {'type': 'walk_completed', 'service_id': scenario.service_id, 'status': 4}
        assert reply == {'type': 'error', 'message': NOT_IN_PROGRESS_MESSAGE}
        await walker.disconnect()

    async def test_disconnect_nao_fecha_o_redis_compartilhado(self):
        scenario = await self.scenario(Service.Status.IN_PROGRESS)
        self.redis.aclose = mock.AsyncMock()
        walker = await self.connect(scenario.service_id, scenario.walker)

        await walker.disconnect()

        self.redis.aclose.assert_not_awaited()


class SharedRedisTests(SimpleTestCase):
    def setUp(self):
        patcher = mock.patch.object(redis_service, '_shared_redis', None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_cria_uma_unica_instancia_sob_demanda(self):
        with mock.patch('redis.asyncio.Redis.from_url', return_value=mock.sentinel.client) as from_url:
            first = redis_service.get_shared_redis()
            second = redis_service.get_shared_redis()

        assert first is mock.sentinel.client
        assert second is first
        from_url.assert_called_once_with(settings.REDIS_URL)
