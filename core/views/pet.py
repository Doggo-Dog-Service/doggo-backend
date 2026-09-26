from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ModelViewSet

from core.models import Pet
from core.serializers import PetDetailSerializer, PetRegisterUpdateSerializer, PetSerializer


class PetViewSet(ModelViewSet):
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PetDetailSerializer
        elif self.action in {'create', 'update', 'partial_update'}:
            return PetRegisterUpdateSerializer
        return PetSerializer

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser:
            queryset = Pet.objects.all()
            return queryset

        if not hasattr(user, 'client_profile'):
            raise PermissionDenied(
                'O usuário precisa ter um perfil de cliente para acessar os pets.'
            )

        return Pet.objects.filter(owner=user.client_profile)
