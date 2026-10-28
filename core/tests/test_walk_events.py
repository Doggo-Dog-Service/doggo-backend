import asyncio
from decimal import Decimal
from unittest import mock

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import InMemoryChannelLayer, get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings
from rest_framework import status

from core.middleware import JWTAuthMiddlewareStack
from core.models import ProviderProfile, Review, Service, WalkEvent
from core.routing import websocket_urlpatterns
from core.tests.helpers import FakeRedis, FlowTestCase, make_provider, make_user, raises
from core.tests.test_consumer import IN_MEMORY_LAYER, RECEIVE_TIMEOUT, build_scenario, token_for
from uploader.models import Image

MAX_PHOTOS = 3
NOTE_MAX = 1000
PHOTO_LIMIT_MESSAGE = 'Limite de 3 fotos por passeio.'
ONLY_IN_PROGRESS_MESSAGE = 'Marcadores só durante o passeio.'


def make_image(name='a'):
    return Image.objects.create(file=f'images/{name}.jpg')


class WalkEventTestCase(FlowTestCase):
    def setUp(self):
        super().setUp()
        self.set_status(Service.Status.IN_PROGRESS)
        self.events_url = self.action_url(self.service, 'events')
        self.note_url = self.action_url(self.service, 'note')

    def set_status(self, new_status):
        Service.objects.filter(pk=self.service.pk).update(status=new_status)
        self.service.refresh_from_db()

    def post_event(self, user, data):
        self.auth(user)
        return self.client.post(self.events_url, data, format='json')


class AddEventTests(WalkEventTestCase):
    def test_passeador_marca_evento_com_posicao(self):
        response = self.post_event(self.walker_user, {'kind': 'pee', 'latitude': -27.5, 'longitude': -48.5})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['kind'] == 'pee'
        assert Decimal(str(response.data['latitude'])) == Decimal('-27.5')
        assert response.data['image_url'] is None
        assert WalkEvent.objects.filter(service=self.service).count() == 1

    def test_evento_sem_posicao_e_salvo_sem_erro(self):
        response = self.post_event(self.walker_user, {'kind': 'water'})

        assert response.status_code == status.HTTP_201_CREATED
        event = WalkEvent.objects.get()
        assert event.latitude is None
        assert event.longitude is None

    def test_tutor_nao_marca_evento(self):
        response = self.post_event(self.tutor_user, {'kind': 'pee'})

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert WalkEvent.objects.count() == 0

    def test_estranho_recebe_404(self):
        response = self.post_event(self.outsider_user, {'kind': 'pee'})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_sem_login_recebe_401(self):
        response = self.client.post(self.events_url, {'kind': 'pee'}, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_fora_de_em_andamento_retorna_409(self):
        self.set_status(Service.Status.CONFIRMED)

        response = self.post_event(self.walker_user, {'kind': 'pee'})

        assert response.status_code == status.HTTP_409_CONFLICT
        assert str(response.data['detail']) == ONLY_IN_PROGRESS_MESSAGE

    def test_so_latitude_ou_so_longitude_retorna_400(self):
        for data in ({'kind': 'pee', 'latitude': -27.5}, {'kind': 'pee', 'longitude': -48.5}):
            response = self.post_event(self.walker_user, data)

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert 'Informe latitude e longitude juntas.' in str(response.data)
        assert WalkEvent.objects.count() == 0

    def test_tipo_invalido_retorna_400(self):
        response = self.post_event(self.walker_user, {'kind': 'xyz'})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_foto_sem_imagem_retorna_400(self):
        response = self.post_event(self.walker_user, {'kind': 'photo'})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'Envie a foto.' in str(response.data)

    def test_foto_com_imagem(self):
        image = make_image()

        response = self.post_event(
            self.walker_user, {'kind': 'photo', 'image_attachment_key': str(image.attachment_key)}
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['image_url'] == image.url

    def test_imagem_em_outro_tipo_e_ignorada(self):
        image = make_image()

        response = self.post_event(self.walker_user, {'kind': 'pee', 'image_attachment_key': str(image.attachment_key)})

        assert response.status_code == status.HTTP_201_CREATED
        assert WalkEvent.objects.get().image is None

    def test_quarta_foto_retorna_409(self):
        for index in range(MAX_PHOTOS):
            image = make_image(f'p{index}')
            response = self.post_event(
                self.walker_user, {'kind': 'photo', 'image_attachment_key': str(image.attachment_key)}
            )
            assert response.status_code == status.HTTP_201_CREATED

        extra = make_image('extra')
        response = self.post_event(
            self.walker_user, {'kind': 'photo', 'image_attachment_key': str(extra.attachment_key)}
        )

        assert response.status_code == status.HTTP_409_CONFLICT
        assert str(response.data['detail']) == PHOTO_LIMIT_MESSAGE
        assert WalkEvent.objects.filter(kind='photo').count() == MAX_PHOTOS

    def test_outros_tipos_nao_contam_no_limite_de_fotos(self):
        for index in range(MAX_PHOTOS):
            WalkEvent.objects.create(service=self.service, kind='photo', image=make_image(f'q{index}'))

        response = self.post_event(self.walker_user, {'kind': 'poop'})

        assert response.status_code == status.HTTP_201_CREATED


class ListEventsTests(WalkEventTestCase):
    def test_participantes_listam_em_ordem(self):
        first = WalkEvent.objects.create(service=self.service, kind='pee')
        second = WalkEvent.objects.create(service=self.service, kind='poop')
        for user in (self.tutor_user, self.walker_user):
            self.auth(user)
            response = self.client.get(self.events_url)

            assert response.status_code == status.HTTP_200_OK
            assert [item['id'] for item in response.data] == [first.pk, second.pk]

    def test_listagem_funciona_apos_conclusao(self):
        WalkEvent.objects.create(service=self.service, kind='pee')
        self.set_status(Service.Status.COMPLETED)
        self.auth(self.tutor_user)

        response = self.client.get(self.events_url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_estranho_recebe_404(self):
        self.auth(self.outsider_user)

        assert self.client.get(self.events_url).status_code == status.HTTP_404_NOT_FOUND

    def test_so_eventos_do_proprio_servico(self):
        other = Service.objects.get(pk=self.service.pk)
        other.pk = None
        other.save()
        WalkEvent.objects.create(service=other, kind='pee')
        self.auth(self.tutor_user)

        assert list(self.client.get(self.events_url).data) == []


class NoteTests(WalkEventTestCase):
    def patch_note(self, user, text):
        self.auth(user)
        return self.client.patch(self.note_url, {'provider_note': text}, format='json')

    def test_passeador_grava_nota_em_andamento(self):
        response = self.patch_note(self.walker_user, 'Foi ótimo')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['provider_note'] == 'Foi ótimo'
        self.service.refresh_from_db()
        assert self.service.provider_note == 'Foi ótimo'

    def test_passeador_grava_nota_apos_concluir(self):
        self.set_status(Service.Status.COMPLETED)

        assert self.patch_note(self.walker_user, 'ok').status_code == status.HTTP_200_OK

    def test_nota_fora_de_andamento_ou_concluido_retorna_409(self):
        self.set_status(Service.Status.CONFIRMED)

        assert self.patch_note(self.walker_user, 'ok').status_code == status.HTTP_409_CONFLICT

    def test_tutor_nao_grava_nota(self):
        assert self.patch_note(self.tutor_user, 'ok').status_code == status.HTTP_403_FORBIDDEN

    def test_estranho_recebe_404(self):
        assert self.patch_note(self.outsider_user, 'ok').status_code == status.HTTP_404_NOT_FOUND

    def test_nota_acima_do_limite_retorna_400(self):
        response = self.patch_note(self.walker_user, 'x' * (NOTE_MAX + 1))

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_nota_no_limite_e_aceita(self):
        assert self.patch_note(self.walker_user, 'x' * NOTE_MAX).status_code == status.HTTP_200_OK

    def test_nota_ausente_retorna_400(self):
        self.auth(self.walker_user)

        assert self.client.patch(self.note_url, {}, format='json').status_code == status.HTTP_400_BAD_REQUEST

    def test_tutor_ve_nota_no_servico(self):
        Service.objects.filter(pk=self.service.pk).update(provider_note='Tudo certo')
        self.auth(self.tutor_user)

        response = self.client.get(f'/api/services/{self.service.pk}/')

        assert response.data['provider_note'] == 'Tudo certo'


class PublishWalkEventTests(WalkEventTestCase):
    def setUp(self):
        super().setUp()
        self.layer = InMemoryChannelLayer()
        patcher = mock.patch('core.services.service_events.get_channel_layer', return_value=self.layer)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.channel = async_to_sync(self.layer.new_channel)()
        async_to_sync(self.layer.group_add)(f'service_{self.service.pk}', self.channel)

    def receive(self):
        return async_to_sync(asyncio.wait_for)(self.layer.receive(self.channel), 1)

    def test_publica_walk_event_apos_commit(self):
        self.auth(self.walker_user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.events_url, {'kind': 'pee'}, format='json')

        message = self.receive()
        assert message['type'] == 'walk_event_message'
        assert message['event'] == {
            'id': response.data['id'],
            'kind': 'pee',
            'latitude': None,
            'longitude': None,
            'image_url': None,
            'created_at': response.data['created_at'],
        }

    def test_nao_publica_antes_do_commit(self):
        self.auth(self.walker_user)
        with self.captureOnCommitCallbacks(execute=False):
            self.client.post(self.events_url, {'kind': 'pee'}, format='json')

        with raises(asyncio.TimeoutError):
            self.receive()

    def test_falha_no_canal_nao_quebra_a_resposta(self):
        self.auth(self.walker_user)
        with mock.patch('core.services.service_events.get_channel_layer', side_effect=RuntimeError('redis fora')):
            with self.assertLogs('core.services.service_events', level='ERROR'):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(self.events_url, {'kind': 'pee'}, format='json')

        assert response.status_code == status.HTTP_201_CREATED


class ReviewListVisibilityTests(FlowTestCase):
    def test_lista_exclui_avaliacoes_de_prestador_nao_aprovado(self):
        hidden_provider = make_provider(
            make_user('pending@test.com'), verification_status=ProviderProfile.Verification.PENDING
        )
        visible = Review.objects.create(provider=self.walker, client=self.tutor, rating=5, comment='ok')
        Review.objects.create(provider=hidden_provider, client=self.tutor, rating=1, comment='oculta')
        self.auth(self.tutor_user)

        response = self.client.get('/api/reviews/')

        assert [item['id'] for item in response.data['results']] == [visible.pk]

    def test_detalhe_de_avaliacao_de_prestador_nao_aprovado_retorna_404(self):
        hidden_provider = make_provider(
            make_user('rejected@test.com'), verification_status=ProviderProfile.Verification.REJECTED
        )
        hidden = Review.objects.create(provider=hidden_provider, client=self.tutor, rating=1, comment='oculta')
        visible = Review.objects.create(provider=self.walker, client=self.tutor, rating=5, comment='ok')
        self.auth(self.tutor_user)

        assert self.client.get(f'/api/reviews/{hidden.pk}/').status_code == status.HTTP_404_NOT_FOUND
        assert self.client.get(f'/api/reviews/{visible.pk}/').status_code == status.HTTP_200_OK


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYER)
class ConsumerWalkEventTests(TransactionTestCase):
    def setUp(self):
        patcher = mock.patch('core.consumers.service_location.get_shared_redis', return_value=FakeRedis())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.application = JWTAuthMiddlewareStack(URLRouter(websocket_urlpatterns))

    async def test_consumer_repassa_walk_event(self):
        scenario = await database_sync_to_async(build_scenario)(Service.Status.IN_PROGRESS)
        communicator = WebsocketCommunicator(
            self.application, f'/ws/services/{scenario.service_id}/?token={token_for(scenario.tutor)}'
        )
        connected, _ = await communicator.connect()
        assert connected
        event = {'id': 7, 'kind': 'pee', 'latitude': None, 'longitude': None, 'image_url': None, 'created_at': 'x'}

        await get_channel_layer().group_send(
            f'service_{scenario.service_id}', {'type': 'walk_event_message', 'event': event}
        )
        message = await communicator.receive_json_from(timeout=RECEIVE_TIMEOUT)

        assert message == {'type': 'walk_event', 'service_id': scenario.service_id, 'event': event}
        await communicator.disconnect()
