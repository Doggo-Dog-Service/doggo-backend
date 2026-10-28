from datetime import time, timedelta
from decimal import Decimal

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import PermissionDenied

from core.models import Service, ServiceLocation
from core.services import booking, service_flow
from core.services.service_flow import Conflict
from core.tests.helpers import (
    SERVICE_DURATION_MINUTES,
    FlowTestCase,
    add_availability,
    make_client,
    make_provider,
    make_service,
    raises,
)
from core.utils.geo import haversine, path_distance

TOLERANCE = 1e-6
POINTS = [(-27.5, -48.5), (-27.501, -48.5), (-27.502, -48.501)]


class ServiceFlowTestCase(FlowTestCase):
    """Fixa o serviço de `setUp` amanhã às 10h locais, longe da virada do dia, e dá helpers de status e HTTP."""

    def setUp(self):
        super().setUp()
        self.start = booking.combine_local(booking.local_now().date() + timedelta(days=1), time(10, 0))
        self.end = self.start + timedelta(minutes=SERVICE_DURATION_MINUTES)
        Service.objects.filter(pk=self.service.pk).update(start_datetime=self.start, end_datetime=self.end)
        self.service.refresh_from_db()

    def set_status(self, new_status):
        Service.objects.filter(pk=self.service.pk).update(status=new_status)
        self.service.refresh_from_db()

    def post_action(self, user, name, service=None):
        self.auth(user)
        return self.client.post(self.action_url(service or self.service, name))


class ServiceFlowTests(ServiceFlowTestCase):
    def test_confirm_pelo_passeador_vai_para_2(self):
        add_availability(self.walker, self.start.date())

        response = self.post_action(self.walker_user, 'confirm')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == Service.Status.CONFIRMED
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.CONFIRMED

    def test_confirm_pelo_tutor_da_403(self):
        add_availability(self.walker, self.start.date())

        response = self.post_action(self.tutor_user, 'confirm')

        assert response.status_code == status.HTTP_403_FORBIDDEN
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.IN_REVIEW

    def test_confirm_por_nao_participante_da_404(self):
        response = self.post_action(self.outsider_user, 'confirm')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_sem_login_da_401(self):
        response = self.client.post(self.action_url(self.service, 'confirm'))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_confirm_fora_de_em_analise_da_409(self):
        add_availability(self.walker, self.start.date())
        self.set_status(Service.Status.CONFIRMED)

        response = self.post_action(self.walker_user, 'confirm')

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_confirm_sem_disponibilidade_da_409(self):
        response = self.post_action(self.walker_user, 'confirm')

        assert response.status_code == status.HTTP_409_CONFLICT
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.IN_REVIEW

    def test_confirm_com_horario_ocupado_da_409(self):
        add_availability(self.walker, self.start.date())
        make_service(self.tutor, self.walker, status=Service.Status.CONFIRMED, start=self.start)

        response = self.post_action(self.walker_user, 'confirm')

        assert response.status_code == status.HTTP_409_CONFLICT
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.IN_REVIEW

    def test_reject_vai_para_6(self):
        response = self.post_action(self.walker_user, 'reject')

        assert response.status_code == status.HTTP_200_OK
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.REJECTED

    def test_reject_pelo_tutor_da_403(self):
        response = self.post_action(self.tutor_user, 'reject')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_cancel_pelo_tutor_em_analise(self):
        response = self.post_action(self.tutor_user, 'cancel')

        assert response.status_code == status.HTTP_200_OK
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.CANCELLED

    def test_cancel_pelo_passeador_confirmado(self):
        self.set_status(Service.Status.CONFIRMED)

        response = self.post_action(self.walker_user, 'cancel')

        assert response.status_code == status.HTTP_200_OK
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.CANCELLED

    def test_cancel_por_nao_participante_da_404(self):
        response = self.post_action(self.outsider_user, 'cancel')

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_cancel_em_andamento_da_409(self):
        self.set_status(Service.Status.IN_PROGRESS)

        response = self.post_action(self.tutor_user, 'cancel')

        assert response.status_code == status.HTTP_409_CONFLICT
        self.service.refresh_from_db()
        assert self.service.status == Service.Status.IN_PROGRESS

    def test_acoes_accept_e_finish_nao_existem(self):
        self.auth(self.walker_user)

        for name in ('accept', 'finish'):
            response = self.client.post(f'/api/services/{self.service.pk}/{name}/')
            assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_usuario_sem_perfil_nao_lista_servicos(self):
        self.auth(self.outsider_user)

        response = self.client.get('/api/services/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == []

    def test_usuario_com_dois_perfis_age_conforme_o_papel_no_servico(self):
        walker_as_client = make_client(self.walker_user)
        tutor_as_provider = make_provider(self.tutor_user)
        add_availability(tutor_as_provider, self.start.date())
        service_b = make_service(walker_as_client, tutor_as_provider, start=self.start)

        confirm_b = self.post_action(self.tutor_user, 'confirm', service_b)
        cancel_original = self.post_action(self.tutor_user, 'cancel')
        confirm_original = self.post_action(self.tutor_user, 'confirm')

        assert confirm_b.status_code == status.HTTP_200_OK
        assert cancel_original.status_code == status.HTTP_200_OK
        assert confirm_original.status_code == status.HTTP_403_FORBIDDEN
        service_b.refresh_from_db()
        assert service_b.status == Service.Status.CONFIRMED


class ServiceStartCompleteTests(ServiceFlowTestCase):
    def test_start_dentro_da_janela_grava_started_at(self):
        self.set_status(Service.Status.CONFIRMED)
        now = self.start - timedelta(minutes=10)

        service_flow.start(self.service, self.walker_user, now=now)

        self.service.refresh_from_db()
        assert self.service.status == Service.Status.IN_PROGRESS
        assert self.service.started_at == now

    def test_start_exatamente_30_min_antes_e_aceito(self):
        self.set_status(Service.Status.CONFIRMED)
        now = self.start - service_flow.START_WINDOW

        service_flow.start(self.service, self.walker_user, now=now)

        self.service.refresh_from_db()
        assert self.service.status == Service.Status.IN_PROGRESS

    def test_start_31_min_antes_da_409(self):
        self.set_status(Service.Status.CONFIRMED)
        now = self.start - service_flow.START_WINDOW - timedelta(seconds=1)

        with raises(Conflict):
            service_flow.start(self.service, self.walker_user, now=now)

        self.service.refresh_from_db()
        assert self.service.status == Service.Status.CONFIRMED
        assert self.service.started_at is None

    def test_start_depois_do_fim_da_409(self):
        self.set_status(Service.Status.CONFIRMED)
        now = self.end + timedelta(seconds=1)

        with raises(Conflict):
            service_flow.start(self.service, self.walker_user, now=now)

        self.service.refresh_from_db()
        assert self.service.status == Service.Status.CONFIRMED

    def test_start_fora_de_confirmado_da_409(self):
        now = self.start - timedelta(minutes=10)

        with raises(Conflict):
            service_flow.start(self.service, self.walker_user, now=now)

        self.service.refresh_from_db()
        assert self.service.status == Service.Status.IN_REVIEW

    def test_start_pelo_tutor_da_403(self):
        self.set_status(Service.Status.CONFIRMED)
        now = self.start - timedelta(minutes=10)

        with raises(PermissionDenied):
            service_flow.start(self.service, self.tutor_user, now=now)

        self.service.refresh_from_db()
        assert self.service.status == Service.Status.CONFIRMED

    def test_start_fora_da_janela_pela_api_da_409(self):
        self.set_status(Service.Status.CONFIRMED)

        response = self.post_action(self.walker_user, 'start')

        assert response.status_code == status.HTTP_409_CONFLICT

    def test_start_e_complete_pela_api(self):
        now = timezone.now()
        service = make_service(self.tutor, self.walker, status=Service.Status.CONFIRMED, start=now)

        started = self.post_action(self.walker_user, 'start', service)
        completed = self.post_action(self.walker_user, 'complete', service)

        assert started.status_code == status.HTTP_200_OK
        assert started.data['status'] == Service.Status.IN_PROGRESS
        assert completed.status_code == status.HTTP_200_OK
        assert completed.data['status'] == Service.Status.COMPLETED

    def test_complete_grava_finished_at_e_distancia(self):
        self.set_status(Service.Status.IN_PROGRESS)
        for latitude, longitude in POINTS:
            ServiceLocation.objects.create(
                service=self.service, latitude=Decimal(str(latitude)), longitude=Decimal(str(longitude))
            )

        service_flow.complete(self.service, self.walker_user)

        self.service.refresh_from_db()
        assert self.service.status == Service.Status.COMPLETED
        assert self.service.finished_at is not None
        assert self.service.distance_meters > 0
        assert abs(self.service.distance_meters - path_distance(POINTS)) < TOLERANCE

    def test_complete_sem_localizacoes_grava_distancia_zero(self):
        self.set_status(Service.Status.IN_PROGRESS)

        service_flow.complete(self.service, self.walker_user)

        self.service.refresh_from_db()
        assert self.service.distance_meters == 0

    def test_complete_fora_de_andamento_da_409(self):
        self.set_status(Service.Status.CONFIRMED)

        with raises(Conflict):
            service_flow.complete(self.service, self.walker_user)

        self.service.refresh_from_db()
        assert self.service.status == Service.Status.CONFIRMED
        assert self.service.finished_at is None

    def test_complete_pelo_tutor_da_403(self):
        self.set_status(Service.Status.IN_PROGRESS)

        with raises(PermissionDenied):
            service_flow.complete(self.service, self.tutor_user)


class PathDistanceTests(SimpleTestCase):
    def test_sem_pontos_ou_com_um_ponto_e_zero(self):
        assert path_distance([]) == 0
        assert path_distance(POINTS[:1]) == 0

    def test_soma_os_trechos_consecutivos(self):
        expected = haversine(*POINTS[0], *POINTS[1]) + haversine(*POINTS[1], *POINTS[2])

        assert abs(path_distance(POINTS) - expected) < TOLERANCE

    def test_aceita_decimal_e_iterador(self):
        decimals = ((Decimal(str(latitude)), Decimal(str(longitude))) for latitude, longitude in POINTS)

        assert abs(path_distance(decimals) - path_distance(POINTS)) < TOLERANCE
