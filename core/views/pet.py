from rest_framework.viewsets import ModelViewSet

from core.models import Pet
from core.serializers import PetDetailSerializer, PetRegisterUpdateSerializer, PetSerializer


class PetViewSet(ModelViewSet):
    queryset = Pet.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PetDetailSerializer
        elif self.action in {'create', 'update', 'partial_update'}:
            return PetRegisterUpdateSerializer
        return PetSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        owner = self.request.query_params.get('owner')

        if owner:
            queryset = queryset.filter(owner=owner)

        return queryset
