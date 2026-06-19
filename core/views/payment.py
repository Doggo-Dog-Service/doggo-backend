from rest_framework.viewsets import ModelViewSet

from core.models import Payment
from core.serializers import PaymentDetailSerializer, PaymentSerializer


class PaymentViewSet(ModelViewSet):
    queryset = Payment.objects.all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PaymentDetailSerializer
        return PaymentSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
