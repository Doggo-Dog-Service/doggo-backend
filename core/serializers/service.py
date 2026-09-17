from django.utils import timezone
from rest_framework import serializers

from core.models import Pet, Service, ServiceType
from core.services import booking


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
    status_label = serializers.CharField(source='get_status_display', read_only=True)

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
            'status_label',
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
    end_datetime = serializers.DateTimeField(required=True)

    class Meta:
        model = Service
        fields = (
            'id',
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
        read_only_fields = ('id', 'client', 'status', 'price', 'created_at')

    def validate(self, data):
        start = self._value(data, 'start_datetime')
        end = self._value(data, 'end_datetime')

        if start is None or end is None:
            raise serializers.ValidationError('Informe o horário inicial e o horário final')
        if end <= start:
            raise serializers.ValidationError('O horário final tem que ser maior que o inicial')
        if timezone.localtime(start) <= booking.local_now():
            raise serializers.ValidationError('O início deve ser no futuro')

        provider = self._value(data, 'provider')
        if provider is None:
            raise serializers.ValidationError('Informe o prestador')

        service_type = self._value(data, 'service_type')
        if service_type is not None and service_type != provider.service_type:
            raise serializers.ValidationError('Tipo de serviço incompatível com o prestador')

        self._validate_pets(data, provider)

        if not booking.fits_in_availability(provider, start, end):
            raise serializers.ValidationError('O horário escolhido não está disponível para este prestador')

        return data

    def _value(self, data, field):
        return data.get(field, getattr(self.instance, field, None))

    def _validate_pets(self, data, provider):
        if self.instance is None:
            client = getattr(self.context['request'].user, 'client_profile', None)
            if client is None:
                raise serializers.ValidationError('Somente clientes podem criar solicitações de serviço')
            if provider.user == self.context['request'].user:
                raise serializers.ValidationError('Você não pode agendar um serviço com você mesmo')
            owner = client
        elif 'pets' not in data:
            return
        else:
            owner = self.instance.client

        if not data.get('pets'):
            raise serializers.ValidationError('Informe ao menos um pet')
        if any(pet.owner != owner for pet in data['pets']):
            raise serializers.ValidationError('Você só pode agendar com seus pets')

    def create(self, validated_data):
        user = self.context['request'].user
        client = getattr(user, 'client_profile', None)

        if client is None:
            raise serializers.ValidationError('Somente clientes podem criar solicitações de serviço')

        provider = validated_data['provider']
        start = validated_data['start_datetime']
        end = validated_data['end_datetime']

        validated_data['price'] = booking.compute_price(provider, start, end)
        validated_data['client'] = client
        validated_data['status'] = Service.Status.IN_REVIEW
        return super().create(validated_data)

    def update(self, instance, validated_data):
        provider = validated_data.get('provider', instance.provider)
        start = validated_data.get('start_datetime', instance.start_datetime)
        end = validated_data.get('end_datetime', instance.end_datetime)

        validated_data['price'] = booking.compute_price(provider, start, end)
        return super().update(instance, validated_data)


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ('id', 'name', 'description', 'providers', 'services')


class ServiceTypeRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ('name', 'description')
