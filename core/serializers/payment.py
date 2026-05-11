from rest_framework import serializers
from core.models import Payment

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            'id',
            'service',
            'amount',
            'paid_at',
            'created_at'
        )

class PaymentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            'id',
            'service',
            'amount',
            'paid_at',
            'created_at'
        )
        depth = 1