from rest_framework.viewsets import ModelViewSet

from core.models import Pet
from core.serializers import PetDetailSerializer, PetSerializer


class PetViewSet(ModelViewSet):
    queryset = Pet.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PetDetailSerializer
        return PetSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        owner_id = self.request.query_params.get('owner_id')

        if owner_id:
            queryset = queryset.filter(owner=owner_id)

        return queryset
