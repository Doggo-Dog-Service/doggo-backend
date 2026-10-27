import asyncio
from datetime import time, timedelta
from unittest import mock

from asgiref.sync import async_to_sync
from channels.layers import InMemoryChannelLayer
from rest_framework import status

from core.models import Service
from core.services import booking, service_flow
from core.tests.helpers import SERVICE_DURATION_MINUTES, FlowTestCase, add_availability, raises

RECEIVE_TIMEOUT = 1


class ServiceEventTests(FlowTestCase):
    """Cada transição aceita publica, após o commit, o evento no grupo `service_{id}` do canal."""

    def setUp(self):
        super().setUp()
        # Amanhã às 10h locais, longe da virada do dia, para a agenda do passeador sempre cobrir o serviço.
        self.start = booking.combine_local(booking.local_now().date() + timedelta(days=1), time(10, 0))
        Service.objects.filter(pk=self.service.pk).update(
            start_datetime=self.start,
            end_datetime=self.start + timedelta(minutes=SERVICE_DURATION_MINUTES),
        )
        self.service.refresh_from_db()

        self.layer = InMemoryChannelLayer()
        patcher = mock.patch('core.services.service_events.get_channel_layer', return_value=self.layer)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.channel = async_to_sync(self.layer.new_channel)()
        async_to_sync(self.layer.group_add)(f'service_{self.service.pk}', self.channel)

    def set_status(self, new_status):
        Service.objects.filter(pk=self.service.pk).update(status=new_status)
        self.service.refresh_from_db()

    def post_action(self, user, name):
        self.auth(user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(self.action_url(self.service, name))

    def receive(self):
        """Próxima mensagem do grupo; falha em vez de travar se nada foi publicado."""
        return async_to_sync(asyncio.wait_for)(self.layer.receive(self.channel), RECEIVE_TIMEOUT)

    def assert_nothing_published(self):
        with raises(TimeoutError):
            self.receive()

    def test_confirm_publica_walk_confirmed(self):
        add_availability(self.walker, self.start.date())

        response = self.post_action(self.walker_user, 'confirm')

        assert response.status_code == status.HTTP_200_OK
        assert self.receive() == {
            'type': 'service_event',
            'event_type': 'walk_confirmed',
            'service_id': self.service.pk,
            'status': Service.Status.CONFIRMED,
        }

    def test_reject_publica_walk_rejected(self):
        response = self.post_action(self.walker_user, 'reject')

        assert response.status_code == status.HTTP_200_OK
        assert self.receive() == {
            'type': 'service_event',
            'event_type': 'walk_rejected',
            'service_id': self.service.pk,
            'status': Service.Status.REJECTED,
        }

    def test_cancel_publica_walk_cancelled(self):
        response = self.post_action(self.tutor_user, 'cancel')

        assert response.status_code == status.HTTP_200_OK
        assert self.receive() == {
            'type': 'service_event',
            'event_type': 'walk_cancelled',
            'service_id': self.service.pk,
            'status': Service.Status.CANCELLED,
        }

    def test_start_publica_walk_started(self):
        self.set_status(Service.Status.CONFIRMED)

        with self.captureOnCommitCallbacks(execute=True):
            service_flow.start(self.service, self.walker_user, now=self.start)

        assert self.receive() == {
            'type': 'service_event',
            'event_type': 'walk_started',
            'service_id': self.service.pk,
            'status': Service.Status.IN_PROGRESS,
        }

    def test_complete_publica_walk_completed(self):
        self.set_status(Service.Status.IN_PROGRESS)

        response = self.post_action(self.walker_user, 'complete')

        assert response.status_code == status.HTTP_200_OK
        assert self.receive() == {
            'type': 'service_event',
            'event_type': 'walk_completed',
            'service_id': self.service.pk,
            'status': Service.Status.COMPLETED,
        }

    def test_evento_so_e_publicado_depois_do_commit(self):
        add_availability(self.walker, self.start.date())
        self.auth(self.walker_user)

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(self.action_url(self.service, 'confirm'))

        assert response.status_code == status.HTTP_200_OK
        assert len(callbacks) == 1
        self.assert_nothing_published()

    def test_falha_ao_publicar_nao_quebra_a_transicao(self):
        add_availability(self.walker, self.start.date())

        with (
            mock.patch('core.services.service_events.get_channel_layer', side_effect=RuntimeError('redis fora do ar')),
            self.assertLogs('core.services.service_events', 'ERROR'),
        ):
            response = self.post_action(self.walker_user, 'confirm')

        assert response.status_code == status.HTTP_200_OK
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.CONFIRMED

    def test_transicao_recusada_nao_publica(self):
        add_availability(self.walker, self.start.date())
        self.auth(self.tutor_user)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(self.action_url(self.service, 'confirm'))

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert len(callbacks) == 0
        self.assert_nothing_published()
