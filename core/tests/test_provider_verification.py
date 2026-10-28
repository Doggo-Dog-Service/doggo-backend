from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from core.models import ProviderDocument, ProviderProfile
from core.tests.helpers import FlowTestCase, add_availability, make_provider, make_user
from uploader.models import Document

PENDING = ProviderProfile.Verification.PENDING
REJECTED = ProviderProfile.Verification.REJECTED
APPROVED = ProviderProfile.Verification.APPROVED
NOT_AVAILABLE_MESSAGE = 'Este passeador ainda não está disponível.'


def documents_url():
    return reverse('providers-my-documents')


def make_document():
    return Document.objects.create(file='documents/x.pdf')


class DocumentsEndpointTests(FlowTestCase):
    def setUp(self):
        super().setUp()
        self.walker.verification_status = PENDING
        self.walker.save()

    def post_document(self, kind='doc_front', document=None):
        document = document or make_document()
        return self.client.post(
            documents_url(),
            {'kind': kind, 'document_attachment_key': str(document.attachment_key)},
            format='json',
        )

    def test_exige_login(self):
        assert self.client.get(documents_url()).status_code == status.HTTP_401_UNAUTHORIZED
        assert self.client.post(documents_url(), {}, format='json').status_code == status.HTTP_401_UNAUTHORIZED

    def test_quem_nao_e_passeador_recebe_403(self):
        self.auth(self.tutor_user)

        assert self.client.get(documents_url()).status_code == status.HTTP_403_FORBIDDEN
        assert self.post_document().status_code == status.HTTP_403_FORBIDDEN

    def test_envia_e_lista_documentos_proprios(self):
        self.auth(self.walker_user)

        assert self.post_document('doc_front').status_code == status.HTTP_201_CREATED
        assert self.post_document('doc_back').status_code == status.HTTP_201_CREATED

        listing = self.client.get(documents_url())
        assert listing.status_code == status.HTTP_200_OK
        assert {item['kind'] for item in listing.data} == {'doc_front', 'doc_back'}
        assert set(listing.data[0]) == {'kind', 'url', 'created_at'}

    def test_lista_nao_mostra_documentos_de_outros(self):
        other = make_provider(make_user('other@test.com'), verification_status=PENDING)
        ProviderDocument.objects.create(provider=other, kind='doc_front', document=make_document())
        self.auth(self.walker_user)

        assert self.client.get(documents_url()).data == []

    def test_reenvio_substitui_o_mesmo_tipo(self):
        self.auth(self.walker_user)
        self.post_document('doc_front')
        new_document = make_document()

        self.post_document('doc_front', new_document)

        docs = ProviderDocument.objects.filter(provider=self.walker)
        assert docs.count() == 1
        assert docs.get().document == new_document

    def test_recusado_que_reenvia_volta_para_pending(self):
        self.walker.verification_status = REJECTED
        self.walker.verification_note = 'Foto ilegível'
        self.walker.save()
        self.auth(self.walker_user)

        assert self.post_document().status_code == status.HTTP_201_CREATED

        self.walker.refresh_from_db()
        assert self.walker.verification_status == PENDING
        assert not self.walker.verification_note

    def test_aprovado_que_reenvia_continua_aprovado(self):
        self.walker.verification_status = APPROVED
        self.walker.save()
        self.auth(self.walker_user)

        self.post_document()

        self.walker.refresh_from_db()
        assert self.walker.verification_status == APPROVED

    def test_validacoes_400(self):
        self.auth(self.walker_user)

        bad_kind = self.client.post(
            documents_url(),
            {'kind': 'selfie', 'document_attachment_key': str(make_document().attachment_key)},
            format='json',
        )
        no_key = self.client.post(documents_url(), {'kind': 'doc_front'}, format='json')
        unknown_key = self.client.post(
            documents_url(),
            {'kind': 'doc_front', 'document_attachment_key': '00000000-0000-0000-0000-000000000000'},
            format='json',
        )

        assert bad_kind.status_code == status.HTTP_400_BAD_REQUEST
        assert no_key.status_code == status.HTTP_400_BAD_REQUEST
        assert unknown_key.status_code == status.HTTP_400_BAD_REQUEST


class VisibilityTests(FlowTestCase):
    def setUp(self):
        super().setUp()
        self.pending = make_provider(make_user('pending@test.com', full_name='Pendente'), verification_status=PENDING)

    def test_lista_so_mostra_aprovados(self):
        self.auth(self.tutor_user)

        response = self.client.get(reverse('providers-list'))

        ids = {item['id'] for item in response.data['results']}
        assert ids == {self.walker.pk}

    def test_lista_esconde_ate_o_proprio_pendente(self):
        self.auth(self.pending.user)

        response = self.client.get(reverse('providers-list'))

        assert self.pending.pk not in {item['id'] for item in response.data['results']}

    def test_busca_so_mostra_aprovados(self):
        self.auth(self.tutor_user)

        response = self.client.get(reverse('search'), {'q': 'Dog'})

        ids = {item['id'] for item in response.data['providers']}
        assert ids == {self.walker.pk}

    def test_detalhe_de_pendente_e_404_para_terceiros(self):
        self.auth(self.tutor_user)

        response = self.client.get(reverse('providers-detail', args=[self.pending.pk]))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_detalhe_de_pendente_para_o_dono_expoe_status(self):
        self.pending.verification_status = REJECTED
        self.pending.verification_note = 'Foto ilegível'
        self.pending.save()
        self.auth(self.pending.user)

        response = self.client.get(reverse('providers-detail', args=[self.pending.pk]))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['verification_status'] == 'rejected'
        assert response.data['verification_note'] == 'Foto ilegível'

    def test_detalhe_de_aprovado_nao_expoe_status_a_terceiros(self):
        self.auth(self.tutor_user)

        response = self.client.get(reverse('providers-detail', args=[self.walker.pk]))

        assert response.status_code == status.HTTP_200_OK
        assert 'verification_status' not in response.data
        assert 'verification_note' not in response.data

    def test_slots_de_pendente_e_404(self):
        self.auth(self.tutor_user)

        response = self.client.get(
            reverse('availability-slots'),
            {'provider': self.pending.pk, 'date': (timezone.localdate() + timedelta(days=1)).isoformat()},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_criar_servico_com_pendente_e_400(self):
        start = timezone.now() + timedelta(days=1, hours=1)
        add_availability(self.pending, timezone.localtime(start).date())
        self.auth(self.tutor_user)

        response = self.client.post(
            reverse('services-list'),
            {
                'pets': [self.pet.pk],
                'provider': self.pending.pk,
                'service_type': self.pending.service_type.pk,
                'start_datetime': start.isoformat(),
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert NOT_AVAILABLE_MESSAGE in str(response.data)

    def test_perfil_proprio_expoe_status_de_verificacao(self):
        self.auth(self.pending.user)

        response = self.client.get(reverse('user_profile'))

        assert response.data['provider_profile']['verification_status'] == 'pending'

    def test_passeador_nao_se_autoaprova(self):
        self.auth(self.pending.user)

        response = self.client.patch(
            reverse('providers-detail', args=[self.pending.pk]),
            {'verification_status': 'approved'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        self.pending.refresh_from_db()
        assert self.pending.verification_status == PENDING
        assert response.data['verification_status'] == 'pending'
