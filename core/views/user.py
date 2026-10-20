from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import User
from core.serializers import UserProfileSerializer, UserRegistrationSerializer, UserSerializer


class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Dados do usuário autenticado",
        description="Retorna os dados do usuário autenticado.",
        responses={200: UserSerializer, 401: None},
    )
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """ Retorna os dados do usuário autenticado."""
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _check_user_permission(self):
        user = self.request.user
        target_user = self.get_object()

        if not user.is_superuser and user.id != target_user.id:
            return Response(
                {'detail': 'Você não tem permissão para modificar este usuário.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return None

    def update(self, request, *args, **kwargs):
        response = self._check_user_permission()

        if response:
            return response

        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        response = self._check_user_permission()

        if response:
            return response

        return super().partial_update(request, *args, **kwargs)


class UserRegistrationView(CreateAPIView):
    """Endpoint para registro de novos usuários."""

    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]


class ProfileView(RetrieveAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
