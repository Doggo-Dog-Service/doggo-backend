from decimal import Decimal
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image as PilImage
from rest_framework import status

from core.models import Payment, Review, ServiceType
from core.tests.helpers import FlowTestCase, make_client, make_provider, make_service, make_service_type, make_user
from uploader.models import Image

IN_MEMORY_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
SIZE_MESSAGE = 'A imagem deve ter no máximo 5 MB.'
FORMAT_MESSAGE = 'Envie uma imagem JPEG ou PNG.'
READ_ONLY_ID_FIELDS = ('providers', 'services')
SERVICE_TYPE_FIELDS = {'id', 'name', 'description', 'duration_minutes'}
TWO_PAYMENTS = 2
REVIEW_RATING = 5


def reviews_list_url():
    return reverse('reviews-list')


def review_detail_url(review):
    return reverse('reviews-detail', args=[review.pk])


def payments_list_url():
    return reverse('payment-list')


def payment_detail_url(payment):
    return reverse('payment-detail', args=[payment.pk])


def service_types_list_url():
    return reverse('type-services-list')


def images_url():
    return reverse('image-list')


def documents_url():
    return reverse('document-list')


def make_staff(email='staff@test.com'):
    user = make_user(email, full_name='Staff')
    user.is_staff = True
    user.save()
    return user


def make_payment(service, user, amount='60.00'):
    return Payment.objects.create(service=service, user=user, amount=Decimal(amount), paid_at=timezone.now())


def image_bytes(image_format='PNG'):
    buffer = BytesIO()
    PilImage.new('RGB', (2, 2)).save(buffer, format=image_format)
    return buffer.getvalue()


class ReviewReadOnlyTestCase(FlowTestCase):
    def setUp(self):
        super().setUp()
        self.review = Review.objects.create(
            provider=self.walker, client=self.tutor, rating=REVIEW_RATING, comment='ótimo'
        )

    def test_reviews_somente_leitura(self):
        self.auth(self.tutor_user)

        responses = [
            self.client.post(reviews_list_url(), {'provider': self.walker.pk, 'rating': 1}),
            self.client.put(review_detail_url(self.review), {'provider': self.walker.pk, 'rating': 1}),
            self.client.patch(review_detail_url(self.review), {'rating': 1}),
            self.client.delete(review_detail_url(self.review)),
        ]

        assert [response.status_code for response in responses] == [status.HTTP_405_METHOD_NOT_ALLOWED] * len(responses)
        self.review.refresh_from_db()
        assert self.review.rating == REVIEW_RATING

    def test_reviews_listadas_por_prestador_incluem_antigas(self):
        old = Review.objects.create(provider=self.walker, client=self.tutor, rating=4, comment='antiga', service=None)
        other_provider = make_provider(make_user('other-walker@test.com'))
        Review.objects.create(provider=other_provider, client=self.tutor, rating=2, comment='de outro')
        self.auth(self.tutor_user)

        response = self.client.get(reviews_list_url(), {'provider_id': self.walker.pk})

        assert response.status_code == status.HTTP_200_OK
        assert {item['id'] for item in response.data['results']} == {self.review.pk, old.pk}
        assert old.service is None


class PaymentAccessTestCase(FlowTestCase):
    def setUp(self):
        super().setUp()
        self.payment = make_payment(self.service, self.tutor_user)
        other_tutor = make_client(make_user('other-tutor@test.com'))
        other_walker = make_provider(make_user('other-walker@test.com'))
        self.other_payment = make_payment(make_service(other_tutor, other_walker), other_tutor.user)

    def test_pagamentos_so_dos_proprios_servicos(self):
        for user in (self.tutor_user, self.walker_user):
            self.auth(user)

            response = self.client.get(payments_list_url())

            assert response.status_code == status.HTTP_200_OK
            assert [item['id'] for item in response.data['results']] == [self.payment.pk]

    def test_pagamento_de_servico_alheio_retorna_404(self):
        self.auth(self.tutor_user)

        response = self.client.get(payment_detail_url(self.other_payment))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_pagamentos_de_usuario_sem_perfil_vem_vazio(self):
        self.auth(self.outsider_user)

        response = self.client.get(payments_list_url())

        assert response.status_code == status.HTTP_200_OK
        assert response.data['results'] == []

    def test_pagamentos_do_prestador_e_do_cliente_aparecem_juntos(self):
        other_payment = make_payment(self.service, self.tutor_user, amount='10.00')
        self.auth(self.walker_user)

        response = self.client.get(payments_list_url())

        ids = [item['id'] for item in response.data['results']]
        assert len(ids) == TWO_PAYMENTS
        assert set(ids) == {self.payment.pk, other_payment.pk}

    def test_post_em_pagamentos_retorna_405(self):
        self.auth(self.tutor_user)

        response = self.client.post(
            payments_list_url(),
            {'service': self.service.pk, 'amount': '1.00', 'paid_at': timezone.now().isoformat()},
        )

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert Payment.objects.count() == TWO_PAYMENTS

    def test_detalhe_do_pagamento_nao_expoe_credenciais_do_pagador(self):
        self.tutor_user.cpf = '52998224725'
        self.tutor_user.save()
        self.auth(self.walker_user)

        response = self.client.get(payment_detail_url(self.payment))

        body = response.content.decode()
        assert response.status_code == status.HTTP_200_OK
        for private in ('password', 'cpf', self.tutor_user.cpf, self.tutor_user.password, self.tutor_user.email):
            assert private not in body
        assert response.data['user']['id'] == self.tutor_user.pk


class ServiceTypeAccessTestCase(FlowTestCase):
    def test_tipo_de_servico_escrita_so_staff(self):
        payload = {'name': 'Hospedagem', 'description': 'Hospedagem de pets'}
        self.auth(self.tutor_user)

        denied = self.client.post(service_types_list_url(), payload)

        assert denied.status_code == status.HTTP_403_FORBIDDEN
        assert not ServiceType.objects.filter(name='Hospedagem').exists()

        self.auth(make_staff())

        created = self.client.post(service_types_list_url(), payload)

        assert created.status_code == status.HTTP_201_CREATED
        assert ServiceType.objects.filter(name='Hospedagem').exists()

    def test_tipo_de_servico_alteracao_so_staff(self):
        service_type = make_service_type('Pet Sitter')
        url = reverse('type-services-detail', args=[service_type.pk])
        self.auth(self.walker_user)

        responses = [self.client.patch(url, {'name': 'X'}), self.client.delete(url)]

        assert [response.status_code for response in responses] == [status.HTTP_403_FORBIDDEN] * len(responses)
        service_type.refresh_from_db()
        assert service_type.name == 'Pet Sitter'

        self.auth(make_staff())

        assert self.client.patch(url, {'name': 'Sitter'}).status_code == status.HTTP_200_OK

    def test_tipo_de_servico_leitura_sem_login(self):
        service_type = self.walker.service_type
        self.client.force_authenticate(user=None)

        listed = self.client.get(service_types_list_url())
        detail = self.client.get(reverse('type-services-detail', args=[service_type.pk]))

        assert listed.status_code == status.HTTP_200_OK
        assert detail.status_code == status.HTTP_200_OK

    def test_tipo_de_servico_sem_listas_de_ids(self):
        self.auth(self.tutor_user)
        service_type = self.walker.service_type

        listed = self.client.get(service_types_list_url())
        detail = self.client.get(reverse('type-services-detail', args=[service_type.pk]))

        item = listed.data['results'][0]
        for body in (item, detail.data):
            assert set(body) == SERVICE_TYPE_FIELDS
            for field in READ_ONLY_ID_FIELDS:
                assert field not in body


# Mantém o upload em memória: o InMemoryStorage não apaga, no Windows, o arquivo temporário usado acima de 2,5 MB.
@override_settings(STORAGES=IN_MEMORY_STORAGES, FILE_UPLOAD_MAX_MEMORY_SIZE=2 * MAX_IMAGE_BYTES)
class ImageUploadTestCase(FlowTestCase):
    def upload(self, data, *, name='a.png', content_type='image/png'):
        file = SimpleUploadedFile(name, data, content_type=content_type)
        return self.client.post(images_url(), {'file': file, 'description': 'foto'}, format='multipart')

    def test_upload_exige_login(self):
        response = self.upload(image_bytes())

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert Image.objects.count() == 0

    def test_upload_sem_listagem(self):
        self.auth(self.tutor_user)

        response = self.client.get(images_url())

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_upload_rejeita_arquivo_falso(self):
        self.auth(self.tutor_user)

        response = self.upload(b'isto nao e uma imagem')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'file' in response.data
        assert Image.objects.count() == 0

    def test_upload_rejeita_formato_que_nao_e_jpeg_nem_png(self):
        self.auth(self.tutor_user)

        response = self.upload(image_bytes('GIF'), name='a.png', content_type='image/png')

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert [str(error) for error in response.data['file']] == [FORMAT_MESSAGE]
        assert Image.objects.count() == 0

    def test_upload_rejeita_acima_de_5mb(self):
        self.auth(self.tutor_user)
        png = image_bytes()

        # Bytes após o IEND são ignorados pelo Pillow: continua sendo um PNG válido, só que grande demais.
        response = self.upload(png + b'\0' * (MAX_IMAGE_BYTES - len(png) + 1))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert [str(error) for error in response.data['file']] == [SIZE_MESSAGE]
        assert Image.objects.count() == 0

    def test_upload_aceita_exatamente_5mb(self):
        self.auth(self.tutor_user)
        png = image_bytes()

        response = self.upload(png + b'\0' * (MAX_IMAGE_BYTES - len(png)))

        assert response.status_code == status.HTTP_201_CREATED
        assert Image.objects.count() == 1

    def test_upload_png_valido(self):
        self.auth(self.tutor_user)

        response = self.upload(image_bytes())

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['attachment_key'] == str(Image.objects.get().attachment_key)

    def test_upload_jpeg_valido(self):
        self.auth(self.tutor_user)

        response = self.upload(image_bytes('JPEG'), name='a.jpg', content_type='image/jpeg')

        assert response.status_code == status.HTTP_201_CREATED
        assert Image.objects.count() == 1


@override_settings(STORAGES=IN_MEMORY_STORAGES)
class DocumentUploadTestCase(FlowTestCase):
    def test_documentos_sem_listagem(self):
        self.auth(self.tutor_user)

        response = self.client.get(documents_url())

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_documentos_exigem_login(self):
        response = self.client.post(documents_url(), {})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
