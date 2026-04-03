from decimal import Decimal

from rest_framework import serializers

from core.models import Service, ServiceType


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = (
            'id',
            'pet',
            'provider',
            'service_type',
            'start_datetime',
            'end_datetime',
            'status',
            'price',
            'created_at',
        )
        read_only_fields = ('id', 'price', 'status', 'created_at')

    def validate(self, data):
        if data['end_datetime'] <= data['start_datetime']:
            raise serializers.ValidationError('O horário final tem que ser maior que o inicial')
        return data

    def create(self, validated_data):
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
            price = provider.price_per_day * days
        else:
            raise serializers.ValidationError('O Provedor não possui preço definido')

        validated_data['price'] = price.quantize(Decimal('0.01'))
        return super().update(instance, validated_data)


class ServiceDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = (
            'id',
            'pet',
            'provider',
            'service_type',
            'start_datetime',
            'end_datetime',
            'status',
            'price',
            'created_at',
        )
        depth = 1


class ServiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceType
        fields = ('id', 'name', 'description', 'providers', 'services')
