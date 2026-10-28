from rest_framework import serializers

from core.models import Payment, User


class PaymentUserSerializer(serializers.ModelSerializer):
    """Pagador exibido ao outro participante do serviço: só identificação, sem credenciais nem dados pessoais."""

    class Meta:
        model = User
        fields = ('id', 'full_name')


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            'id',
            'user',
            'service',
            'amount',
            'paid_at',
            'created_at'
        )
        read_only_fields = ['user']


class PaymentDetailSerializer(serializers.ModelSerializer):
    user = PaymentUserSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = (
            'id',
            'user',
            'service',
            'amount',
            'paid_at',
            'created_at'
        )
        depth = 1
