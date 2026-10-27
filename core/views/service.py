from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
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
)
from core.services import booking, service_flow
from core.services.service_flow import Conflict


class ServiceViewSet(ModelViewSet):
    queryset = Service.objects.all()
    permission_classes = [IsAuthenticated, IsServiceOwnerOrProvider]

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return ServiceCreateUpdateSerializer
        return ServiceListSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Service.objects.none()

        # Quem não participa do serviço (como cliente ou prestador) recebe 404 em qualquer ação.
        queryset = Service.objects.filter(Q(client__user=user) | Q(provider__user=user))

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
        if service.status != Service.Status.IN_REVIEW:
            raise Conflict('Serviço não pode ser excluído')
        service.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

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
