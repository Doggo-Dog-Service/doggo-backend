from rest_framework import serializers

from core.models import ClientProfile, Review, User


class ReviewUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'full_name',
            'profile_picture',
        )


class ReviewClientSerializer(serializers.ModelSerializer):
    user = ReviewUserSerializer(read_only=True)

    class Meta:
        model = ClientProfile
        fields = (
            'id',
            'user',
        )


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
    client = ReviewClientSerializer(read_only=True)

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
        depth = 1
