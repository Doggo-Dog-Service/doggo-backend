from rest_framework.exceptions import ValidationError
from rest_framework.viewsets import ReadOnlyModelViewSet

from core.models import ProviderProfile, Review
from core.serializers import ReviewDetailSerializer, ReviewSerializer


class ReviewViewSet(ReadOnlyModelViewSet):
    """Avaliações são somente leitura: nascem em `POST /services/{id}/rate/`, depois de o passeio ser concluído."""

    queryset = Review.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ReviewDetailSerializer
        return ReviewSerializer

    def get_queryset(self):
        queryset = super().get_queryset().order_by('-created_at', '-id')

        if self.action == 'list':
            # Avaliações de passeadores não aprovados não aparecem na listagem pública.
            queryset = queryset.filter(provider__verification_status=ProviderProfile.Verification.APPROVED)

        provider_id = self.request.query_params.get('provider_id')

        if provider_id:
            try:
                queryset = queryset.filter(provider=int(provider_id))
            except ValueError:
                raise ValidationError({'provider_id': 'Informe um número inteiro'}) from None

        return queryset
