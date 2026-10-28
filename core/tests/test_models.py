from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import ClientProfile, ProviderProfile, Review, Service
from core.tests.helpers import (
    make_client,
    make_provider,
    make_service,
    make_service_type,
    make_user,
    raises,
)

NOTA_ALTA = 4
NOTA_BAIXA = 2
TOTAL_AVALIACOES = 2
MEDIA_ESPERADA = 3.0
DISTANCIA_METROS = 1234.5


class ModelsTestCase(TestCase):
    def setUp(self):
        self.service_type = make_service_type()
        self.client_profile = make_client(make_user('cliente@test.com'))
        self.provider = make_provider(make_user('prestador@test.com'), service_type=self.service_type)

    def make_review(self, rating=5, service=None):
        return Review.objects.create(
            provider=self.provider,
            client=self.client_profile,
            rating=rating,
            service=service,
        )


class ReviewServiceTests(ModelsTestCase):
    def test_review_unica_por_servico(self):
        service = make_service(self.client_profile, self.provider)
        self.make_review(service=service)

        with raises(IntegrityError), transaction.atomic():
            self.make_review(rating=3, service=service)

    def test_review_sem_servico_continua_valida(self):
        review = Review(provider=self.provider, client=self.client_profile, rating=NOTA_ALTA, service=None, comment='')

        review.full_clean()
        review.save()

        assert Review.objects.get(pk=review.pk).service is None

    def test_varias_reviews_sem_servico_sao_permitidas(self):
        self.make_review(rating=NOTA_ALTA)
        self.make_review(rating=NOTA_BAIXA)

        assert Review.objects.filter(service__isnull=True).count() == TOTAL_AVALIACOES

    def test_servico_expoe_review_pelo_related_name(self):
        service = make_service(self.client_profile, self.provider)
        review = self.make_review(service=service)

        assert service.review == review

    def test_comentario_tem_valor_padrao_vazio(self):
        review = self.make_review()

        review.refresh_from_db()
        assert not review.comment


class ServiceFlowFieldsTests(ModelsTestCase):
    def test_campos_de_conclusao_comecam_vazios(self):
        service = make_service(self.client_profile, self.provider)

        assert service.finished_at is None
        assert service.distance_meters is None

    def test_campos_de_conclusao_sao_persistidos(self):
        service = make_service(self.client_profile, self.provider)
        service.finished_at = service.start_datetime
        service.distance_meters = DISTANCIA_METROS
        service.save()

        service.refresh_from_db()
        assert service.finished_at == service.start_datetime
        assert service.distance_meters == DISTANCIA_METROS


class LongitudeValidatorTests(ModelsTestCase):
    def test_longitude_aceita_menos_120(self):
        profile = ProviderProfile(
            user=make_user('novo@test.com'),
            fixed_latitude=Decimal('-27.5'),
            fixed_longitude=Decimal('-120.0'),
            last_longitude=Decimal('-120.0'),
            service_type=self.service_type,
        )

        profile.full_clean()

    def test_longitude_aceita_limites_de_180(self):
        profile = ClientProfile(user=make_user('limite@test.com'), last_longitude=Decimal('180'))
        profile.full_clean()

        profile.last_longitude = Decimal('-180')
        profile.full_clean()

    def test_longitude_rejeita_acima_de_180(self):
        for campo, perfil in (
            ('fixed_longitude', ProviderProfile(fixed_longitude=Decimal('180.5'))),
            ('last_longitude', ProviderProfile(last_longitude=Decimal('-180.5'))),
            ('last_longitude', ClientProfile(last_longitude=Decimal('181'))),
        ):
            with self.subTest(campo=campo, perfil=type(perfil).__name__):
                with raises(ValidationError) as erro:
                    perfil.full_clean()
                assert campo in erro.exception.message_dict

    def test_latitude_continua_limitada_a_90(self):
        profile = ProviderProfile(fixed_latitude=Decimal('91'))

        with raises(ValidationError) as erro:
            profile.full_clean()
        assert 'fixed_latitude' in erro.exception.message_dict


class WithRatingTests(ModelsTestCase):
    def test_with_rating_inclui_reviews_sem_servico(self):
        service = make_service(self.client_profile, self.provider)
        self.make_review(rating=NOTA_ALTA, service=service)
        self.make_review(rating=NOTA_BAIXA, service=None)

        provider = ProviderProfile.objects.with_rating().get(pk=self.provider.pk)

        assert provider.rating_avg == MEDIA_ESPERADA
        assert provider.rating_count == TOTAL_AVALIACOES

    def test_with_rating_sem_reviews(self):
        provider = ProviderProfile.objects.with_rating().get(pk=self.provider.pk)

        assert provider.rating_avg is None
        assert provider.rating_count == 0

    def test_with_rating_nao_duplica_prestadores_com_varios_servicos(self):
        for _ in range(3):
            make_service(self.client_profile, self.provider, status=Service.Status.COMPLETED)
        self.make_review(rating=5)

        providers = list(ProviderProfile.objects.with_rating())

        assert len(providers) == 1
        assert providers[0].rating_count == 1

    def test_manager_padrao_continua_funcional(self):
        assert ProviderProfile.objects.get(pk=self.provider.pk) == self.provider
        assert ProviderProfile.objects.filter(is_active=True).count() == 1
        assert ProviderProfile.objects.all().count() == 1
