from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from core.models import Pet, Service, ServiceLocation, ServiceType
from core.services import booking

CONTACT_VISIBLE_STATUSES = {Service.Status.CONFIRMED, Service.Status.IN_PROGRESS}


class PetServiceSerializer(serializers.ModelSerializer):
    pet_picture = serializers.SerializerMethodField()

    class Meta:
        model = Pet
        fields = (
            'id',
            'pet_picture',
            'name',
            'breed',
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
    duration = serializers.SerializerMethodField()
    distance = serializers.SerializerMethodField()
    contact_phone = serializers.SerializerMethodField()
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
            'started_at',
            'finished_at',
            'duration',
            'distance',
            'contact_phone',
            'is_rating',
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

    def get_duration(self, obj) -> str | None:
        if not obj.started_at or not obj.finished_at:
            return None

        total_seconds = int((obj.finished_at - obj.started_at).total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def get_distance(self, obj) -> float | None:
        # Gravada na conclusão do passeio (service_flow.complete); não varre as localizações a cada serialização.
        if obj.distance_meters is None:
            return None
        return round(obj.distance_meters, 2)

    def get_contact_phone(self, obj) -> str | None:
        """Telefone da outra parte, visível só enquanto o serviço está Confirmado ou Em andamento."""
        request = self.context.get('request')
        if request is None or obj.status not in CONTACT_VISIBLE_STATUSES:
            return None

        if obj.client.user_id == request.user.id:
            return obj.provider.user.phone
        if obj.provider.user_id == request.user.id:
            return obj.client.user.phone
        return None


class ServiceCreateUpdateSerializer(serializers.ModelSerializer):
    end_datetime = serializers.DateTimeField(required=False)

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

        if start is None:
            raise serializers.ValidationError('Informe o horário inicial')

        provider = self._value(data, 'provider')
        if provider is None:
            raise serializers.ValidationError('Informe o prestador')

        # O cliente informa apenas o início; a duração vem do tipo de serviço do prestador.
        end = self._value(data, 'end_datetime')
        if end is None:
            duration_minutes = provider.service_type.duration_minutes
            if duration_minutes <= 0:
                raise serializers.ValidationError('O tipo de serviço deste prestador não tem duração definida')
            end = start + timedelta(minutes=duration_minutes)
            data['end_datetime'] = end

        if end <= start:
            raise serializers.ValidationError('O horário final tem que ser maior que o inicial')
        if timezone.localtime(start) <= booking.local_now():
            raise serializers.ValidationError('O início deve ser no futuro')

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


class ServiceUpdateSerializer(serializers.ModelSerializer):
    """PATCH do tutor: troca os pets e/ou o início. Fim e preço são sempre recalculados a partir do início."""

    pets = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Pet.objects.all(),
        allow_empty=False,
        error_messages={'empty': 'Informe ao menos um pet'},
    )

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
        read_only_fields = (
            'id',
            'provider',
            'client',
            'service_type',
            'end_datetime',
            'status',
            'price',
            'created_at',
        )

    def validate_pets(self, pets):
        if any(pet.owner_id != self.instance.client_id for pet in pets):
            raise serializers.ValidationError('Você só pode agendar com seus pets')
        return pets

    def validate(self, data):
        if 'start_datetime' not in data:
            return data

        provider = self.instance.provider
        start = data['start_datetime']

        duration_minutes = provider.service_type.duration_minutes
        if duration_minutes <= 0:
            raise serializers.ValidationError('O tipo de serviço deste prestador não tem duração definida')
        end = start + timedelta(minutes=duration_minutes)

        if timezone.localtime(start) <= booking.local_now():
            raise serializers.ValidationError('O início deve ser no futuro')
        if not booking.fits_in_availability(provider, start, end):
            raise serializers.ValidationError('O horário escolhido não está disponível para este prestador')

        data['end_datetime'] = end
        data['price'] = booking.compute_price(provider, start, end)
        return data


class ServiceRateSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, default='')


class ServiceRoutePointSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()

    class Meta:
        model = ServiceLocation
        fields = ('latitude', 'longitude', 'created_at')


class ServiceRouteSerializer(serializers.Serializer):
    service_id = serializers.IntegerField()
    status = serializers.IntegerField()
    started_at = serializers.DateTimeField(allow_null=True)
    finished_at = serializers.DateTimeField(allow_null=True)
    duration_seconds = serializers.IntegerField(allow_null=True)
    distance_meters = serializers.FloatField(allow_null=True)
    points = ServiceRoutePointSerializer(many=True)


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ('id', 'name', 'description', 'duration_minutes')


class ServiceTypeRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ('name', 'description')
