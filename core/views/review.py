from rest_framework.viewsets import ModelViewSet

from core.models import Review
from core.serializers import (
    ReviewDetailSerializer,
    ReviewSerializer,
)


class ReviewViewSet(ModelViewSet):
    queryset = Review.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ReviewDetailSerializer

        return ReviewSerializer
