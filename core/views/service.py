from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import ProviderProfile, Service, ServiceType
from core.permissions import IsServiceOwnerOrProvider
from core.serializers import (
    ReviewSerializer,
    ServiceCreateUpdateSerializer,
    ServiceListSerializer,
    ServiceRateSerializer,
    ServiceRouteSerializer,
    ServiceTypeRegisterSerializer,
    ServiceTypeSerializer,
    ServiceUpdateSerializer,
)
from core.services import booking, service_flow
from core.services.service_flow import Conflict


class ServiceViewSet(ModelViewSet):
    queryset = Service.objects.all()
    permission_classes = [IsAuthenticated, IsServiceOwnerOrProvider]
    # Serviço não se apaga nem se substitui por inteiro: o fluxo é cancelar/recusar e editar com PATCH.
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    # Filtros da listagem (query string) -> lookup no model; só valem em `list`.
    list_filters = {'status': 'status', 'provider': 'provider_id', 'client': 'client_id'}

    def get_serializer_class(self):
        if self.action == 'create':
            return ServiceCreateUpdateSerializer
        if self.action == 'partial_update':
            return ServiceUpdateSerializer
        return ServiceListSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Service.objects.none()

        # Quem não participa do serviço (como cliente ou prestador) recebe 404 em qualquer ação.
        queryset = (
            Service.objects.filter(Q(client__user=user) | Q(provider__user=user))
            .select_related('client__user__profile_picture', 'provider__user__profile_picture', 'service_type')
            .prefetch_related('pets__pet_picture')
        )

        if self.action == 'list':
            queryset = self._apply_list_filters(queryset)

        return queryset.order_by('-created_at')

    def _apply_list_filters(self, queryset):
        for param, lookup in self.list_filters.items():
            value = self.request.query_params.get(param)
            if not value:
                continue
            try:
                number = int(value)
            except ValueError:
                raise ValidationError({param: 'Informe um número inteiro'}) from None
            queryset = queryset.filter(**{lookup: number})
        return queryset

    def get_object(self):
        service = super().get_object()
        if self.action == 'partial_update':
            # Falha cedo (403/409), antes de validar o corpo; `perform_update` repete a checagem sob lock.
            service_flow.require_editable(service, self.request.user)
        return service

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

    def perform_update(self, serializer):
        service = serializer.instance
        data = serializer.validated_data

        with transaction.atomic():
            # Mesma ordem de trava de `service_flow.confirm` (prestador, depois serviço).
            ProviderProfile.objects.select_for_update().get(pk=service.provider_id)
            service_flow.require_editable(Service.objects.select_for_update().get(pk=service.pk), self.request.user)
            if 'start_datetime' in data and booking.has_conflict(
                service.provider,
                data['start_datetime'],
                data['end_datetime'],
                exclude_pk=service.pk,
            ):
                raise Conflict('Horário indisponível para este prestador')
            serializer.save()

    @extend_schema(request=None, responses=ServiceListSerializer)
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        service = service_flow.confirm(self.get_object(), request.user)
        return Response(self.get_serializer(service).data)

    @extend_schema(request=None, responses=ServiceListSerializer)
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        service = service_flow.reject(self.get_object(), request.user)
        return Response(self.get_serializer(service).data)

    @extend_schema(request=None, responses=ServiceListSerializer)
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        service = service_flow.cancel(self.get_object(), request.user)
        return Response(self.get_serializer(service).data)

    @extend_schema(request=None, responses=ServiceListSerializer)
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        service = service_flow.start(self.get_object(), request.user)
        return Response(self.get_serializer(service).data)

    @extend_schema(request=None, responses=ServiceListSerializer)
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        service = service_flow.complete(self.get_object(), request.user)
        return Response(self.get_serializer(service).data)

    @extend_schema(request=ServiceRateSerializer, responses={201: ReviewSerializer})
    @action(detail=True, methods=['post'])
    def rate(self, request, pk=None):
        service = self.get_object()
        serializer = ServiceRateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = service_flow.rate(service, request.user, **serializer.validated_data)
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses=ServiceRouteSerializer)
    @action(detail=True, methods=['get'])
    def route(self, request, pk=None):
        route = service_flow.route_summary(self.get_object())
        return Response(ServiceRouteSerializer(route).data)


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
