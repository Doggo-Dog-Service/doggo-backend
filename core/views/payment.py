from django.db.models import Q
from rest_framework.viewsets import ReadOnlyModelViewSet

from core.models import Payment
from core.serializers import PaymentDetailSerializer, PaymentSerializer


class PaymentViewSet(ReadOnlyModelViewSet):
    """Pagamentos só podem ser lidos, e apenas por quem participa do serviço (cliente ou prestador)."""

    queryset = Payment.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PaymentDetailSerializer
        return PaymentSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Payment.objects.none()

        return (
            Payment.objects.filter(Q(service__client__user=user) | Q(service__provider__user=user))
            .select_related('user', 'service')
            .order_by('-paid_at', '-id')
        )
