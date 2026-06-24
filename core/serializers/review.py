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
    client_name = serializers.CharField(source='client.user.full_name')
    client_picture = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = (
            'id',
            'provider',
            'client_name',
            'client_picture',
            'rating',
            'comment',
            'created_at',
        )
        read_only_fields = ('id', 'created_at',)

    def get_client_picture(self, obj):
        if obj.client.user.profile_picture:
            return obj.client.user.profile_picture.url
        return None


class ReviewCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = (
            'provider',
            'client',
            'rating',
            'comment'
        )
        read_only_fields = ('client', )

    def create(self, validated_data):
        user = self.context['request'].user
        try:
            validated_data['client'] = user.client_profile
        except ClientProfile.DoesNotExist:
            raise serializers.ValidationError(
                'Usuário não possui perfil de Cliente'
            )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user = self.context['request'].user

        if instance.client.user.id == user.id:
            return super().update(instance, validated_data)

        raise serializers.ValidationError(
            'Você não tem permissão para fazer mudanças nesse comentário'
        )


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
