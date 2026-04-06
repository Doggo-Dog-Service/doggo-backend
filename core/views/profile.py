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
