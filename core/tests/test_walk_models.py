from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase

from core.models import ProviderDocument, ProviderProfile, Service, WalkEvent
from core.tests.helpers import make_client, make_provider, make_service, make_user, raises
from uploader.models import Document


def make_document():
    return Document.objects.create(file='documents/x.pdf')


class WalkEventTests(TestCase):
    def setUp(self):
        self.service = make_service(make_client(make_user('t@test.com')), make_provider(make_user('p@test.com')))

    def test_eventos_ordenados_por_criacao(self):
        first = WalkEvent.objects.create(service=self.service, kind=WalkEvent.Kind.PEE)
        second = WalkEvent.objects.create(service=self.service, kind=WalkEvent.Kind.POOP)
        third = WalkEvent.objects.create(service=self.service, kind=WalkEvent.Kind.WATER)

        assert list(self.service.events.all()) == [first, second, third]

    def test_evento_aceita_posicao_e_imagem_vazias(self):
        event = WalkEvent.objects.create(service=self.service, kind=WalkEvent.Kind.PHOTO)

        assert event.latitude is None
        assert event.longitude is None
        assert event.image is None

    def test_provider_note_comeca_vazia(self):
        assert not self.service.provider_note
        assert not Service.objects.get(pk=self.service.pk).provider_note


class ProviderVerificationTests(TestCase):
    def test_default_pending_no_model(self):
        provider = make_provider(make_user('p@test.com'), verification_status=ProviderProfile.Verification.PENDING)

        assert provider.verification_status == 'pending'
        assert not provider.verification_note

    def test_documento_unico_por_tipo(self):
        provider = make_provider(make_user('p@test.com'))
        ProviderDocument.objects.create(
            provider=provider, kind=ProviderDocument.Kind.DOC_FRONT, document=make_document()
        )

        with raises(IntegrityError), transaction.atomic():
            ProviderDocument.objects.create(
                provider=provider, kind=ProviderDocument.Kind.DOC_FRONT, document=make_document()
            )

        ProviderDocument.objects.create(
            provider=provider, kind=ProviderDocument.Kind.DOC_BACK, document=make_document()
        )
        assert provider.documents.count() == 2  # noqa: PLR2004


class ProviderAdminActionTests(TestCase):
    def setUp(self):
        self.model_admin = admin.site._registry[ProviderProfile]
        self.provider = make_provider(
            make_user('p@test.com'),
            verification_status=ProviderProfile.Verification.REJECTED,
        )
        self.provider.verification_note = 'Foto ilegível'
        self.provider.save()
        self.request = RequestFactory().post('/')
        self.request.session = {}
        self.request._messages = FallbackStorage(self.request)  # noqa: SLF001

    def run_action(self, name):
        queryset = ProviderProfile.objects.filter(pk=self.provider.pk)
        getattr(self.model_admin, name)(self.request, queryset)
        self.provider.refresh_from_db()

    def test_aprovar_limpa_nota(self):
        self.run_action('approve_providers')

        assert self.provider.verification_status == 'approved'
        assert not self.provider.verification_note

    def test_recusar_marca_rejected_e_preserva_motivo(self):
        self.provider.verification_status = ProviderProfile.Verification.PENDING
        self.provider.save()

        self.run_action('reject_providers')

        assert self.provider.verification_status == 'rejected'
        assert self.provider.verification_note == 'Foto ilegível'

    def test_filtro_por_status_e_inline_de_documentos(self):
        assert 'verification_status' in self.model_admin.list_filter
        assert self.model_admin.inlines
