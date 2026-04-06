from rest_framework import serializers

from core.models import ClientProfile, Pet


class PetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pet
        fields = (
            'id',
            'owner',
            'name',
            'breed',
            'size',
            'weight',
            'notes',
            'vaccination_status',
            'created_at'
        )
        read_only_fields = ('id', 'owner', 'created_at')

    def create(self, validated_data):
        user = self.context['request'].user

        try:
            validated_data['owner'] = user.client_profile
        except ClientProfile.DoesNotExist:
            raise serializers.ValidationError('Usuário não possui perfil de Cliente')

        return super().create(validated_data)


class PetDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pet
        fields = (
            'id',
            'owner',
            'name',
            'breed',
            'size',
            'weight',
            'notes',
            'vaccination_status',
            'created_at'
        )
        read_only_fields = ('id', 'owner', 'created_at')
        depth = 2
