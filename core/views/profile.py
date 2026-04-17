from rest_framework.viewsets import ModelViewSet

from core.models import ClientProfile, ProviderProfile
from core.serializers import ClientDetailSerializer, ClientSerializer, ProviderDetailSerializer, ProviderSerializer


class ClientViewSet(ModelViewSet):
    queryset = ClientProfile.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ClientDetailSerializer
        return ClientSerializer


class ProviderViewSet(ModelViewSet):
    queryset = ProviderProfile.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProviderDetailSerializer
        return ProviderSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        service_type = self.request.query_params.get('service_type')
        is_active = self.request.query_params.get('is_active')

        if service_type:
            queryset = queryset.filter(service_type=service_type)

        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')

        return queryset
