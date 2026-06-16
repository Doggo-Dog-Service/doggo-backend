from rest_framework import serializers

from core.models import ClientProfile, Review


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = (
            'id',
            'provider',
            'client',
            'rating',
            'comment',
            'created_at',
        )
        read_only_fields = ('id', 'client', 'created_at',)

    def create(self, validated_data):
        user = self.context['request'].user
        try:
            validated_data['client'] = user.client_profile
        except ClientProfile.DoesNotExist:
            raise serializers.ValidationError(
                'Usuário não possui perfil de Cliente'
            )
        return super().create(validated_data)


class ReviewDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = (
            'id',
            'provider',
            'client',
            'rating',
            'comment',
            'created_at',
        )
        read_only_fields = ('id', 'client', 'created_at',)
        depth = 2
