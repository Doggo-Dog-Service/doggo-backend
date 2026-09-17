from datetime import date, timedelta

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import ProviderAvailability, ProviderProfile, ServiceType
from core.permissions import IsProviderAvailabilityOwnerOrReadOnly
from core.serializers import (
    ProviderAvailabilityCreateUpdateSerializer,
    ProviderAvailabilitySerializer,
)
from core.services import booking


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

    @extend_schema(
        parameters=[
            OpenApiParameter('provider', int, required=True),
            OpenApiParameter('date', str, required=True),
            OpenApiParameter('duration_minutes', int, required=True),
            OpenApiParameter('service', int, required=False),
        ],
    )
    @action(detail=False, methods=['get'])
    def slots(self, request):
        provider_id = request.query_params.get('provider')
        date_param = request.query_params.get('date')
        duration_param = request.query_params.get('duration_minutes')
        service_id = request.query_params.get('service')

        if not provider_id:
            raise ValidationError('Informe o provider')
        if not date_param:
            raise ValidationError('Informe a data')
        if not duration_param:
            raise ValidationError('Informe a duração em minutos')

        try:
            provider = ProviderProfile.objects.get(pk=provider_id)
        except ProviderProfile.DoesNotExist:
            raise NotFound('Provider não encontrado')

        try:
            target = date.fromisoformat(date_param)
        except ValueError:
            raise ValidationError('Data inválida. Use o formato AAAA-MM-DD')

        try:
            duration_minutes = int(duration_param)
        except (TypeError, ValueError):
            raise ValidationError('Duração inválida. Use minutos inteiros')
        if duration_minutes <= 0:
            raise ValidationError('A duração deve ser maior que zero')
        duration = timedelta(minutes=duration_minutes)

        if service_id:
            try:
                service_type = ServiceType.objects.get(pk=service_id)
            except ServiceType.DoesNotExist:
                raise NotFound('Serviço não encontrado')
            if service_type != provider.service_type:
                raise ValidationError('Tipo de serviço incompatível com o provider')

        if booking.local_now().date() > target:
            raise ValidationError('A data deve ser hoje ou futura')

        slots = booking.generate_slots(provider, target, duration)
        return Response(
            {
                'provider': provider.id,
                'date': target.isoformat(),
                'duration_minutes': duration_minutes,
                'available_slots': [booking.format_slot(slot) for slot in slots],
            }
        )
