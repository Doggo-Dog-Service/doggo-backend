from rest_framework.viewsets import ModelViewSet

from core.models import Review
from core.serializers import (
    ReviewCreateUpdateSerializer,
    ReviewDetailSerializer,
    ReviewSerializer,
)


class ReviewViewSet(ModelViewSet):
    queryset = Review.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ReviewDetailSerializer
        if self.action in {'create', 'update', 'partial_update'}:
            return ReviewCreateUpdateSerializer
        return ReviewSerializer

    def get_queryset(self):
        queryset = super().get_queryset()

        provider_id = self.request.query_params.get('provider_id')

        if provider_id:
            queryset = queryset.filter(provider=provider_id)

        return queryset
