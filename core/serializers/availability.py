from rest_framework import serializers

from core.models import ProviderAvailability, ProviderProfile


class ProviderAvailabilitySerializer(serializers.ModelSerializer):
    weekday_label = serializers.CharField(source='get_weekday_display', read_only=True)

    class Meta:
        model = ProviderAvailability
        fields = (
            'id',
            'provider',
            'weekday',
            'weekday_label',
            'start_time',
            'end_time',
        )
        read_only_fields = ('id', 'provider',)


class ProviderAvailabilityCreateUpdateSerializer(serializers.ModelSerializer):
    weekday_label = serializers.CharField(source='get_weekday_display', read_only=True)

    class Meta:
        model = ProviderAvailability
        fields = (
            'id',
            'provider',
            'weekday',
            'weekday_label',
            'start_time',
            'end_time',
        )
        read_only_fields = ('id', 'provider',)

    def validate(self, data):
        start_time = data.get('start_time', getattr(self.instance, 'start_time', None))
        end_time = data.get('end_time', getattr(self.instance, 'end_time', None))

        if start_time is None or end_time is None:
            raise serializers.ValidationError('Informe o horário inicial e o horário final')

        if start_time >= end_time:
            raise serializers.ValidationError('O horário final tem que ser maior que o inicial')

        return data

    def create(self, validated_data):
        user = self.context['request'].user
        try:
            provider = user.provider_profile
        except ProviderProfile.DoesNotExist:
            raise serializers.ValidationError('Usuário não possui perfil de Prestador')

        validated_data['provider'] = provider
        self._check_overlap(
            provider,
            validated_data['weekday'],
            validated_data['start_time'],
            validated_data['end_time'],
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        provider = instance.provider
        weekday = validated_data.get('weekday', instance.weekday)
        start_time = validated_data.get('start_time', instance.start_time)
        end_time = validated_data.get('end_time', instance.end_time)

        self._check_overlap(provider, weekday, start_time, end_time, exclude_pk=instance.pk)
        return super().update(instance, validated_data)

    @staticmethod
    def _check_overlap(provider, weekday, start_time, end_time, exclude_pk=None):
        queryset = ProviderAvailability.objects.filter(
            provider=provider,
            weekday=weekday,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if exclude_pk is not None:
            queryset = queryset.exclude(pk=exclude_pk)

        if queryset.exists():
            raise serializers.ValidationError('Já existe disponibilidade neste período para este dia')
