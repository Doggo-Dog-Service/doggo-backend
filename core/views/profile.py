from decimal import Decimal, InvalidOperation

from django.db.models import ProtectedError, Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import ClientProfile, ProviderProfile
from core.permissions import IsProfileOwnerOrReadOnly
from core.serializers import (
    ClientDetailSerializer,
    ClientSerializer,
    ProviderDetailSerializer,
    ProviderDocumentCreateSerializer,
    ProviderDocumentSerializer,
    ProviderRegisterSerializer,
    ProviderSerializer,
)
from core.services import provider_verification
from core.services.service_flow import Conflict
from core.utils.geo import haversine_annotation

PROFILE_DELETE_BLOCKED_MESSAGE = 'Não é possível excluir o perfil: há passeios ou avaliações vinculados.'


class ProtectedDestroyMixin:
    """Perfil com passeios ou avaliações (FKs PROTECT) não pode ser excluído: responde 409 em vez de 500."""

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as error:
            raise Conflict(PROFILE_DELETE_BLOCKED_MESSAGE) from error


class ClientViewSet(ProtectedDestroyMixin, ModelViewSet):
    queryset = ClientProfile.objects.all()

    def get_queryset(self):
        # Perfil de cliente é privado (tem localização): cada usuário enxerga só o próprio; os demais recebem 404.
        user = self.request.user
        if not user.is_authenticated:
            return ClientProfile.objects.none()
        return ClientProfile.objects.filter(user=user).order_by('id')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ClientDetailSerializer
        return ClientSerializer


class ProviderViewSet(ProtectedDestroyMixin, ModelViewSet):
    queryset = (
        ProviderProfile.objects.with_rating().select_related('user__profile_picture', 'service_type').order_by('id')
    )
    permission_classes = [IsAuthenticated, IsProfileOwnerOrReadOnly]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProviderDetailSerializer
        elif self.action in {'create', 'update', 'partial_update'}:
            return ProviderRegisterSerializer
        return ProviderSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.action == 'my_documents':
            return queryset
        if self.action != 'list':
            # Passeador não aprovado só é visível (e editável) para o próprio dono; os demais recebem 404.
            return queryset.filter(
                Q(verification_status=ProviderProfile.Verification.APPROVED) | Q(user=self.request.user)
            )

        queryset = queryset.approved()

        params = self.request.query_params

        service_type = params.get('service_type')
        if service_type:
            queryset = queryset.filter(service_type=service_type)

        is_active = params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        min_price = self._as_decimal(params.get('min_price'))
        if min_price is not None:
            queryset = queryset.filter(price_per_hour__gte=min_price)

        max_price = self._as_decimal(params.get('max_price'))
        if max_price is not None:
            queryset = queryset.filter(price_per_hour__lte=max_price)

        lat = self._as_float(params.get('lat'))
        lon = self._as_float(params.get('lon'))

        if lat is not None and lon is not None:
            queryset = queryset.annotate(distance=haversine_annotation(lat, lon))

            max_distance = self._as_float(params.get('max_distance'))
            if max_distance is not None:
                queryset = queryset.filter(distance__lte=max_distance).order_by('distance')

        return queryset

    @extend_schema(
        methods=['GET'],
        responses=ProviderDocumentSerializer(many=True),
        summary='Lista os documentos do próprio passeador',
    )
    @extend_schema(
        methods=['POST'],
        request=ProviderDocumentCreateSerializer,
        responses={201: ProviderDocumentSerializer},
        summary='Envia ou substitui um documento do passeador',
    )
    @action(
        detail=False, methods=['get', 'post'], url_path='me/documents', url_name='my-documents', pagination_class=None
    )
    def my_documents(self, request):
        provider = getattr(request.user, 'provider_profile', None)
        if provider is None:
            raise PermissionDenied('Somente passeadores enviam documentos.')

        if request.method == 'GET':
            return Response(ProviderDocumentSerializer(provider.documents.select_related('document'), many=True).data)

        serializer = ProviderDocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = provider_verification.submit_document(
            provider, serializer.validated_data['kind'], serializer.validated_data['document_attachment_key']
        )
        return Response(ProviderDocumentSerializer(record).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _as_decimal(value):
        if not value:
            return None
        try:
            return Decimal(value)
        except InvalidOperation:
            return None

    @staticmethod
    def _as_float(value):
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            return None
