from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from core.models import Service, ServiceType
from core.serializers import (
    ServiceCreateUpdateSerializer,
    ServiceListSerializer,
    ServiceTypeRegisterSerializer,
    ServiceTypeSerializer,
)


class ServiceViewSet(ModelViewSet):
    queryset = Service.objects.all()

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return ServiceCreateUpdateSerializer
        return ServiceListSerializer


class ServiceTypeViewSet(ModelViewSet):
    queryset = ServiceType.objects.all()

    def get_serializer_class(self):
        if self.action == 'create':
            return ServiceTypeRegisterSerializer
        return ServiceTypeSerializer

    def get_permissions(self):
        if self.action in {'list', 'retrieve'}:
            return [AllowAny()]
        return [IsAuthenticated()]
