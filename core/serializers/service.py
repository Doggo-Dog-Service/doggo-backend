from decimal import Decimal

from rest_framework import serializers

from core.models import Pet, Service, ServiceType


class PetServiceSerializer(serializers.ModelSerializer):
    pet_picture = serializers.SerializerMethodField()

    class Meta:
        model = Pet
        fields = (
            'id',
            'pet_picture',
            'name',
        )

    def get_pet_picture(self, obj):
        pet_picture = obj.pet_picture
        if pet_picture:
            return pet_picture.url
        return None


class ServiceListSerializer(serializers.ModelSerializer):
    client_id = serializers.IntegerField(source='client.id')
    client_name = serializers.CharField(source='client.user.full_name')
    client_picture = serializers.SerializerMethodField()
    provider_id = serializers.IntegerField(source='provider.id')
    provider_name = serializers.CharField(source='provider.user.full_name')
    provider_picture = serializers.SerializerMethodField()
    service_type = serializers.CharField(source='service_type.name')
    pets = PetServiceSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = (
            'id',
            'client_id',
            'client_name',
            'client_picture',
            'provider_id',
            'provider_name',
            'provider_picture',
            'service_type',
            'pets',
            'price',
            'status',
            'start_datetime',
            'end_datetime',
            'created_at'
        )

    def get_client_picture(self, obj):
        profile_picture = obj.client.user.profile_picture
        if profile_picture:
            return profile_picture.url
        return None

    def get_provider_picture(self, obj):
        profile_picture = obj.provider.user.profile_picture
        if profile_picture:
            return profile_picture.url
        return None


class ServiceCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = (
            'pets',
            'provider',
            'client',
            'service_type',
            'start_datetime',
            'end_datetime',
            'status',
            'price',
            'created_at',
        )
        read_only_fields = ('id', 'client', 'price', 'status', 'created_at')

    def validate(self, data):
        if data['end_datetime'] <= data['start_datetime']:
            raise serializers.ValidationError('O horário final tem que ser maior que o inicial')
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        client = getattr(user, 'client_profile', None)

        if client is None:
            raise serializers.ValidationError('Somente clientes podem criar solicitações de serviço')

        provider = validated_data['provider']
        start = validated_data['start_datetime']
        end = validated_data['end_datetime']

        duration = end - start
        hours = Decimal(duration.total_seconds()) / Decimal(3600)

        if provider.price_per_hour:
            price = provider.price_per_hour * hours
        elif provider.price_per_day:
            days = duration.days or 1
            price = provider.price_per_day * Decimal(days)
        else:
            raise serializers.ValidationError('O Provedor não possui preço definido')

        validated_data['price'] = price.quantize(Decimal('0.01'))
        validated_data['client'] = client
        return super().create(validated_data)

    def update(self, instance, validated_data):
        provider = validated_data.get('provider', instance.provider)
        start = validated_data.get('start_datetime', instance.start_datetime)
        end = validated_data.get('end_datetime', instance.end_datetime)

        duration = end - start
        hours = Decimal(duration.total_seconds()) / Decimal(3600)

        if provider.price_per_hour:
            price = provider.price_per_hour * hours
        elif provider.price_per_day:
            days = duration.days or 1
            price = provider.price_per_day * Decimal(days)
        else:
            raise serializers.ValidationError('O Provedor não possui preço definido')

        validated_data['price'] = price.quantize(Decimal('0.01'))
        return super().update(instance, validated_data)


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ('id', 'name', 'description', 'providers', 'services')


class ServiceTypeRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ('name', 'description')
