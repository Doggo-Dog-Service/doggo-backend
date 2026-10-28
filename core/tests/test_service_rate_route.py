from datetime import timedelta
from decimal import Decimal
from unittest import mock

import redis
from channels.layers import InMemoryChannelLayer
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework import status

from core.models import Review, Service, ServiceLocation
from core.services import redis_service
from core.services.redis_service import RedisService, clear_service_location
from core.tests.helpers import FlowTestCase, make_service
from core.utils.geo import path_distance

POINTS = [(-27.5, -48.5), (-27.501, -48.5), (-27.502, -48.501)]
SAVED_DISTANCE = 1234.5
TOP_RATING = 5
DISTANCE_TOLERANCE = 1e-6


def create_points(service, points=POINTS):
    return [
        ServiceLocation.objects.create(
            service=service, latitude=Decimal(str(latitude)), longitude=Decimal(str(longitude))
        )
        for latitude, longitude in points
    ]


class ServiceRateTests(FlowTestCase):
    def setUp(self):
        super().setUp()
        self.service = make_service(self.tutor, self.walker, status=Service.Status.COMPLETED, pets=[self.pet])

    def rate(self, user, payload):
        self.auth(user)
        return self.client.post(self.action_url(self.service, 'rate'), payload, format='json')

    def test_rate_cria_review_ligada_ao_servico(self):
        response = self.rate(self.tutor_user, {'rating': 5, 'comment': 'Ótimo'})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['rating'] == TOP_RATING
        assert response.data['comment'] == 'Ótimo'
        review = Review.objects.get(service=self.service)
        assert review.provider == self.walker
        assert review.client == self.tutor
        assert review.rating == TOP_RATING
        self.service.refresh_from_db()
        assert self.service.is_rating is True

    def test_rate_sem_comentario_e_aceito(self):
        response = self.rate(self.tutor_user, {'rating': 4})

        assert response.status_code == status.HTTP_201_CREATED
        assert not Review.objects.get(service=self.service).comment

    def test_rate_duplicado_da_409(self):
        first = self.rate(self.tutor_user, {'rating': 5})
        second = self.rate(self.tutor_user, {'rating': 1})

        assert first.status_code == status.HTTP_201_CREATED
        assert second.status_code == status.HTTP_409_CONFLICT
        assert Review.objects.filter(service=self.service).count() == 1
        assert Review.objects.get(service=self.service).rating == TOP_RATING

    def test_rate_antes_de_concluir_da_409(self):
        Service.objects.filter(pk=self.service.pk).update(status=Service.Status.IN_PROGRESS)

        response = self.rate(self.tutor_user, {'rating': 5})

        assert response.status_code == status.HTTP_409_CONFLICT
        assert not Review.objects.filter(service=self.service).exists()
        self.service.refresh_from_db()
        assert self.service.is_rating is False

    def test_rate_pelo_passeador_da_403(self):
        response = self.rate(self.walker_user, {'rating': 5})

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not Review.objects.filter(service=self.service).exists()

    def test_rate_por_nao_participante_da_404(self):
        response = self.rate(self.outsider_user, {'rating': 5})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_rate_sem_login_da_401(self):
        response = self.client.post(self.action_url(self.service, 'rate'), {'rating': 5}, format='json')

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_rate_nota_invalida_da_400(self):
        for rating in (0, 6):
            response = self.rate(self.tutor_user, {'rating': rating})

            assert response.status_code == status.HTTP_400_BAD_REQUEST, rating
        assert not Review.objects.filter(service=self.service).exists()

    def test_rate_sem_nota_da_400(self):
        response = self.rate(self.tutor_user, {'comment': 'Sem nota'})

        assert response.status_code == status.HTTP_400_BAD_REQUEST


class ServiceRouteTests(FlowTestCase):
    def route(self, user, service=None):
        self.auth(user)
        return self.client.get(self.action_url(service or self.service, 'route'))

    def test_route_devolve_pontos_em_ordem(self):
        service = make_service(self.tutor, self.walker, status=Service.Status.IN_PROGRESS, pets=[self.pet])
        first, second, third = create_points(service)
        now = timezone.now()
        # Fora da ordem de criação: por created_at a sequência correta é third, first, second.
        for point, minutes in ((first, 5), (second, 10), (third, 1)):
            ServiceLocation.objects.filter(pk=point.pk).update(created_at=now + timedelta(minutes=minutes))

        response = self.route(self.tutor_user, service)

        assert response.status_code == status.HTTP_200_OK
        assert [(point['latitude'], point['longitude']) for point in response.data['points']] == [
            (-27.502, -48.501),
            (-27.5, -48.5),
            (-27.501, -48.5),
        ]
        assert response.data['points'][0]['created_at'] is not None

    def test_route_em_andamento_calcula_distancia(self):
        started_at = timezone.now() - timedelta(minutes=20)
        service = make_service(self.tutor, self.walker, status=Service.Status.IN_PROGRESS, pets=[self.pet])
        Service.objects.filter(pk=service.pk).update(started_at=started_at)
        create_points(service)

        response = self.route(self.walker_user, service)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['service_id'] == service.pk
        assert response.data['status'] == Service.Status.IN_PROGRESS
        assert response.data['finished_at'] is None
        assert abs(response.data['distance_meters'] - path_distance(POINTS)) < DISTANCE_TOLERANCE
        assert 20 * 60 <= response.data['duration_seconds'] < 21 * 60

    def test_route_concluido_usa_distancia_salva(self):
        started_at = timezone.now() - timedelta(hours=1)
        finished_at = started_at + timedelta(minutes=45)
        service = make_service(self.tutor, self.walker, status=Service.Status.COMPLETED, pets=[self.pet])
        Service.objects.filter(pk=service.pk).update(
            started_at=started_at, finished_at=finished_at, distance_meters=SAVED_DISTANCE
        )
        create_points(service)

        response = self.route(self.tutor_user, service)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['distance_meters'] == SAVED_DISTANCE
        assert response.data['duration_seconds'] == 45 * 60
        assert response.data['finished_at'] is not None

    def test_route_sem_inicio_nem_pontos_devolve_nulos(self):
        response = self.route(self.tutor_user)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['points'] == []
        assert response.data['started_at'] is None
        assert response.data['duration_seconds'] is None
        assert response.data['distance_meters'] == 0

    def test_route_por_nao_participante_da_404(self):
        response = self.route(self.outsider_user)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_route_sem_login_da_401(self):
        response = self.client.get(self.action_url(self.service, 'route'))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class CompleteClearsRedisTests(FlowTestCase):
    def setUp(self):
        super().setUp()
        self.service = make_service(self.tutor, self.walker, status=Service.Status.IN_PROGRESS, pets=[self.pet])
        # `complete` também publica o evento no commit: o layer em memória evita tocar no Redis real.
        patcher = mock.patch('core.services.service_events.get_channel_layer', return_value=InMemoryChannelLayer())
        patcher.start()
        self.addCleanup(patcher.stop)

    def complete(self):
        self.auth(self.walker_user)
        return self.client.post(self.action_url(self.service, 'complete'))

    def test_complete_limpa_redis_apos_commit(self):
        with mock.patch.object(redis_service, 'clear_service_location') as clear:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.complete()
                clear.assert_not_called()

        assert response.status_code == status.HTTP_200_OK
        clear.assert_called_once_with(self.service.pk)

    def test_complete_nao_limpa_redis_quando_a_transicao_falha(self):
        Service.objects.filter(pk=self.service.pk).update(status=Service.Status.CONFIRMED)

        with mock.patch.object(redis_service, 'clear_service_location') as clear:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.complete()

        assert response.status_code == status.HTTP_409_CONFLICT
        clear.assert_not_called()

    def test_complete_com_redis_fora_do_ar_responde_200(self):
        with mock.patch('redis.Redis.from_url', side_effect=redis.ConnectionError):
            with self.assertLogs('core.services.redis_service', 'ERROR'):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.complete()

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == Service.Status.COMPLETED
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.COMPLETED


@override_settings(REDIS_URL='redis://redis.test:6379')
class ClearServiceLocationTests(SimpleTestCase):
    def test_apaga_as_tres_chaves_do_servico(self):
        with mock.patch('redis.Redis.from_url') as from_url:
            clear_service_location(7)

        from_url.assert_called_once_with('redis://redis.test:6379', socket_connect_timeout=1, socket_timeout=1)
        client = from_url.return_value
        client.delete.assert_called_once_with(
            RedisService.get_location_key(7),
            RedisService.get_saved_location_key(7),
            RedisService.get_distance_key(7),
        )
        client.close.assert_called_once_with()

    def test_erro_ao_apagar_e_registrado_e_nao_propaga(self):
        with mock.patch('redis.Redis.from_url') as from_url:
            from_url.return_value.delete.side_effect = redis.TimeoutError
            with self.assertLogs('core.services.redis_service', 'ERROR'):
                clear_service_location(7)

        from_url.return_value.close.assert_called_once_with()
