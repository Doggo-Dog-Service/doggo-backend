from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import ProviderProfile, Service, ServiceType
from core.permissions import IsServiceOwnerOrProvider
from core.serializers import (
    ServiceCreateUpdateSerializer,
    ServiceListSerializer,
    ServiceTypeRegisterSerializer,
    ServiceTypeSerializer,
)
from core.services import booking


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = 'Conflito com outro agendamento'
    default_code = 'conflict'


class ServiceViewSet(ModelViewSet):
    queryset = Service.objects.all()
    permission_classes = [IsAuthenticated, IsServiceOwnerOrProvider]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return ServiceCreateUpdateSerializer
        return ServiceListSerializer

    def get_queryset(self):
        if self.action != 'list':
            return Service.objects.all()

        user = self.request.user

        filters = Q()
        if hasattr(user, 'client_profile'):
            filters |= Q(client=user.client_profile)
        if hasattr(user, 'provider_profile'):
            filters |= Q(provider=user.provider_profile)

        queryset = Service.objects.filter(filters) if filters else Service.objects.none()

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        provider_param = self.request.query_params.get('provider')
        if provider_param:
            queryset = queryset.filter(provider_id=provider_param)

        client_param = self.request.query_params.get('client')
        if client_param:
            queryset = queryset.filter(client_id=client_param)

        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        with transaction.atomic():
            provider = serializer.validated_data['provider']
            ProviderProfile.objects.select_for_update().get(pk=provider.pk)
            if booking.has_conflict(
                provider,
                serializer.validated_data['start_datetime'],
                serializer.validated_data['end_datetime'],
            ):
                raise Conflict('Horário indisponível para este prestador')
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        service = self.get_object()
        if service.status != booking.IN_REVIEW_STATUS:
            raise Conflict('Serviço não pode ser excluído')
        service.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        service = self.get_object()
        if service.provider.user != request.user:
            raise PermissionDenied('Ação disponível apenas para o prestador')
        if service.status != booking.IN_REVIEW_STATUS:
            raise Conflict('Serviço não está pendente')

        with transaction.atomic():
            ProviderProfile.objects.select_for_update().get(pk=service.provider.pk)
            service = Service.objects.select_for_update().get(pk=service.pk)
            if service.status != booking.IN_REVIEW_STATUS:
                raise Conflict('Serviço não está pendente')
            if not booking.fits_in_availability(
                service.provider, service.start_datetime, service.end_datetime
            ):
                raise Conflict('O horário não está mais disponível para este prestador')
            if booking.has_conflict(
                service.provider,
                service.start_datetime,
                service.end_datetime,
                exclude_pk=service.pk,
            ):
                raise Conflict('Horário em conflito com outro serviço')
            service.status = Service.Status.CONFIRMED
            service.save(update_fields=['status'])

        return Response(self.get_serializer(service).data)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        service = self.get_object()
        if service.provider.user != request.user:
            raise PermissionDenied('Ação disponível apenas para o prestador')
        if service.status != booking.IN_REVIEW_STATUS:
            raise Conflict('Serviço não está pendente')
        service.status = Service.Status.REJECTED
        service.save(update_fields=['status'])
        return Response(self.get_serializer(service).data)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        service = self.get_object()
        if service.client.user != request.user:
            raise PermissionDenied('Ação disponível apenas para o cliente')
        if service.status != booking.IN_REVIEW_STATUS:
            raise Conflict('Serviço não está pendente')
        service.status = Service.Status.CANCELLED
        service.save(update_fields=['status'])
        return Response(self.get_serializer(service).data)

    @extend_schema(request=None)
    @action(detail=True, methods=['post'])
    def finish(self, request, pk=None):
        service = self.get_object()
        if service.provider.user != request.user:
            raise PermissionDenied('Ação disponível apenas para o prestador')
        if service.status != booking.IN_PROGRESS_STATUS:
            raise Conflict('Serviço não está em andamento')
        service.status = Service.Status.COMPLETED
        service.save(update_fields=['status'])
        return Response(self.get_serializer(service).data)


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
