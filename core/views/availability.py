from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from core.models import ProviderAvailability
from core.permissions import IsProviderAvailabilityOwnerOrReadOnly
from core.serializers import (
    ProviderAvailabilityCreateUpdateSerializer,
    ProviderAvailabilitySerializer,
)


class ProviderAvailabilityViewSet(ModelViewSet):
    queryset = ProviderAvailability.objects.all()
    permission_classes = [IsAuthenticated, IsProviderAvailabilityOwnerOrReadOnly]
    pagination_class = None

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return ProviderAvailabilityCreateUpdateSerializer
        return ProviderAvailabilitySerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        provider_id = self.request.query_params.get('provider_id')
        if provider_id:
            return queryset.filter(provider_id=provider_id)

        if self.action == 'list':
            user = self.request.user
            if hasattr(user, 'provider_profile'):
                return queryset.filter(provider=user.provider_profile)
            return queryset.none()

        return queryset
