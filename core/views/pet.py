from rest_framework.viewsets import ModelViewSet

from core.models import Pet
from core.serializers import PetDetailSerializer, PetSerializer


class PetViewSet(ModelViewSet):
    queryset = Pet.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PetDetailSerializer
        return PetSerializer
