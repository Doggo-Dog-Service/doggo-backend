from decimal import Decimal, InvalidOperation

from django.db.models import ProtectedError
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from core.models import ClientProfile, ProviderProfile
from core.permissions import IsProfileOwnerOrReadOnly
from core.serializers import (
    ClientDetailSerializer,
    ClientSerializer,
    ProviderDetailSerializer,
    ProviderRegisterSerializer,
    ProviderSerializer,
)
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
        ProviderProfile.objects.with_rating()
        .select_related('user__profile_picture', 'service_type')
        .order_by('id')
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

        if self.action != 'list':
            return queryset

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
