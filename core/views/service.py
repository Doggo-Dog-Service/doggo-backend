from rest_framework.viewsets import ModelViewSet

from core.models import Service, ServiceType
from core.serializers import ServiceDetailSerializer, ServiceSerializer, ServiceTypeSerializer


class ServiceViewSet(ModelViewSet):
    queryset = Service.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ServiceDetailSerializer
        return ServiceSerializer


class ServiceTypeViewSet(ModelViewSet):
    queryset = ServiceType.objects.all()
    serializer_class = ServiceTypeSerializer
