from rest_framework import serializers

from core.models import ClientProfile, ProviderProfile
from core.serializers.availability import ProviderAvailabilitySerializer
from core.serializers.pet import PetSerializer
from core.serializers.user import UserSerializer

CLIENT_DUPLICATE_MESSAGE = 'Usuário já possui perfil de cliente.'
PROVIDER_DUPLICATE_MESSAGE = 'Usuário já possui perfil de prestador.'


class ClientSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = ClientProfile
        fields = ('id', 'user', 'last_latitude', 'last_longitude', 'created_at')

    def validate(self, attrs):
        user = self.context['request'].user
        if self.instance is None and ClientProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError(CLIENT_DUPLICATE_MESSAGE)
        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ClientDetailSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    pets = PetSerializer(many=True, read_only=True)

    class Meta:
        model = ClientProfile
        fields = ('id', 'user', 'pets', 'last_latitude', 'last_longitude', 'created_at')


class ProviderSerializer(serializers.ModelSerializer):
    # `rating_avg` e `rating_count` vêm de `ProviderProfile.objects.with_rating()`.
    classification = serializers.FloatField(source='rating_avg', read_only=True)
    rating_count = serializers.IntegerField(read_only=True)
    service_type_name = serializers.CharField(source='service_type.name', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    profile_picture = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()

    class Meta:
        model = ProviderProfile
        fields = (
            'id',
            'profile_picture',
            'full_name',
            'service_type_name',
            'price_per_hour',
            'price_per_day',
            'fixed_latitude',
            'fixed_longitude',
            'classification',
            'rating_count',
            'distance',
            'is_active',
            'created_at',
        )

    def get_profile_picture(self, obj):
        if obj.user.profile_picture:
            return obj.user.profile_picture.url
        return None

    def get_distance(self, obj):
        return getattr(obj, 'distance', None)


class ProviderRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderProfile
        fields = (
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

    def validate(self, attrs):
        user = self.context['request'].user
        if self.instance is None and ProviderProfile.objects.filter(user=user).exists():
            raise serializers.ValidationError(PROVIDER_DUPLICATE_MESSAGE)
        return attrs

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ProviderDetailSerializer(serializers.ModelSerializer):
    # `rating_avg` e `rating_count` vêm de `ProviderProfile.objects.with_rating()`.
    classification = serializers.FloatField(source='rating_avg', read_only=True)
    rating_count = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    profile_picture = serializers.SerializerMethodField()
    service_type_name = serializers.CharField(source='service_type.name', read_only=True)
    availability = ProviderAvailabilitySerializer(many=True, read_only=True)

    class Meta:
        model = ProviderProfile
        fields = (
            'id',
            'full_name',
            'profile_picture',
            'fixed_latitude',
            'fixed_longitude',
            'service_type_name',
            'price_per_hour',
            'price_per_day',
            'description',
            'is_active',
            'created_at',
            'classification',
            'rating_count',
            'reviews',
            'availability',
        )

    def get_profile_picture(self, obj):
        if obj.user.profile_picture:
            return obj.user.profile_picture.url
        return None
