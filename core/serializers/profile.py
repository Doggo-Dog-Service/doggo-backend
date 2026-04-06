from rest_framework import serializers

from core.models import ClientProfile, ProviderProfile
from core.serializers.user import UserSerializer


class ClientSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ClientProfile
        fields = (
            'id',
            'user',
            'last_latitude',
            'last_longitude',
            'created_at'
        )

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ClientDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProfile
        fields = (
            'id',
            'user',
            'pets',
            'last_latitude',
            'last_longitude',
            'created_at'
        )
        depth = 1


class ProviderSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ProviderProfile
        fields = (
            'id',
            'user',
            'fixed_latitude',
            'fixed_longitude',
            'last_latitude',
            'last_longitude',
            'service_type',
            'price_per_hour',
            'price_per_day',
            'description',
            'is_active',
            'created_at',
        )

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ProviderDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderProfile
        fields = (
            'id',
            'user',
            'fixed_latitude',
            'fixed_longitude',
            'last_latitude',
            'last_longitude',
            'service_type',
            'price_per_hour',
            'price_per_day',
            'services',
            'description',
            'is_active',
            'created_at',
        )
        depth = 1
