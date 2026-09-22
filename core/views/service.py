from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import Service, ServiceType
from core.serializers import (
    ServiceCreateUpdateSerializer,
    ServiceListSerializer,
    ServiceTypeRegisterSerializer,
    ServiceTypeSerializer,
)
from core.services import publish_service_event
from core.utils.geo import haversine


class ServiceViewSet(ModelViewSet):
    queryset = Service.objects.all()

    def get_serializer_class(self):
        if self.action in {'create', 'update', 'partial_update'}:
            return ServiceCreateUpdateSerializer
        return ServiceListSerializer

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        service = self.get_object()

        if service.provider.user != request.user:
            return Response(
                {"detail": "Apenas o prestador pode confirmar o passeio."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if Service.Status(int(service.status)) != Service.Status.IN_REVIEW:
            return Response(
                {"detail": f"Não é possível confirmar: status atual é {service.get_status_display()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            service.status = Service.Status.CONFIRMED
            service.save(update_fields=["status"])

            transaction.on_commit(
                lambda: publish_service_event(
                    service.id, "walk_confirmed", Service.Status.CONFIRMED
                )
            )

        return Response(ServiceListSerializer(service).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        service = self.get_object()

        if service.provider.user != request.user:
            return Response(
                {"detail": "Apenas o prestador pode recusar o passeio."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if Service.Status(int(service.status)) != Service.Status.IN_REVIEW:
            return Response(
                {"detail": f"Não é possível recusar: status atual é {service.get_status_display()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            service.status = Service.Status.REJECTED
            service.save(update_fields=["status"])

            transaction.on_commit(
                lambda: publish_service_event(
                    service.id, "walk_rejected", Service.Status.REJECTED
                )
            )

        return Response(ServiceListSerializer(service).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        service = self.get_object()

        if service.provider.user != request.user:
            return Response(
                {"detail": "Apenas o prestador pode iniciar o passeio."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if Service.Status(int(service.status)) != Service.Status.CONFIRMED:
            return Response(
                {"detail": f"Não é possível iniciar: status atual é {service.get_status_display()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            service.status = Service.Status.IN_PROGRESS
            service.save(update_fields=["status"])

            transaction.on_commit(
                lambda: publish_service_event(
                    service.id, "walk_started", Service.Status.IN_PROGRESS
                )
            )

        return Response(ServiceListSerializer(service).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        service = self.get_object()

        if service.provider.user != request.user:
            return Response(
                {"detail": "Apenas o prestador pode concluir o passeio."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if Service.Status(int(service.status)) != Service.Status.IN_PROGRESS:
            return Response(
                {"detail": "Apenas passeios em andamento podem ser concluídos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            service.status = Service.Status.COMPLETED
            service.end_datetime = timezone.now()
            service.save(update_fields=["status", "end_datetime"])

            transaction.on_commit(
                lambda: publish_service_event(
                    service.id, "walk_completed", Service.Status.COMPLETED
                )
            )

        return Response(ServiceListSerializer(service).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        service = self.get_object()

        user = request.user
        if service.provider.user != user and service.client.user != user:  # noqa: PLR1714
            return Response(
                {"detail": "Apenas o prestador ou o cliente podem cancelar."},
                status=status.HTTP_403_FORBIDDEN,
            )

        cancellable = {
            Service.Status.IN_REVIEW,
            Service.Status.CONFIRMED,
            Service.Status.IN_PROGRESS,
        }

        if Service.Status(int(service.status)) not in cancellable:
            return Response(
                {"detail": f"Não é possível cancelar: status atual é {service.get_status_display()}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            service.status = Service.Status.CANCELLED
            service.save(update_fields=["status"])

            transaction.on_commit(
                lambda: publish_service_event(
                    service.id, "walk_cancelled", Service.Status.CANCELLED
                )
            )

        return Response(ServiceListSerializer(service).data)

    @action(detail=True, methods=["get"])
    def route(self, request, pk=None):
        service = self.get_object()

        user = request.user
        if service.provider.user != user and service.client.user != user:  # noqa: PLR1714
            return Response(
                {"detail": "Apenas os envolvidos no passeio podem ver a rota."},
                status=status.HTTP_403_FORBIDDEN,
            )

        locations = list(
            service.locations.order_by("created_at").values_list(
                "latitude", "longitude", "created_at"
            )
        )

        total_distance = 0.0
        for index in range(1, len(locations)):
            current = locations[index - 1]
            following = locations[index]
            total_distance += haversine(
                current[0],
                current[1],
                following[0],
                following[1],
            )

        points = [
            {
                "latitude": float(latitude),
                "longitude": float(longitude),
                "created_at": created_at,
            }
            for latitude, longitude, created_at in locations
        ]

        return Response(
            {
                "points": points,
                "total_distance": round(total_distance, 2),
            }
        )


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
