from rest_framework import serializers
from rest_framework.serializers import SlugRelatedField

from core.models import ClientProfile, Pet
from uploader.models import Image
from uploader.serializers import ImageSerializer


class PetSerializer(serializers.ModelSerializer):
    pet_profile_attachment_key = SlugRelatedField(
        source='pet_profile',
        queryset=Image,
        slug_field='attachment_key',
        required=False,
        write_only=True,
    )
    pet_profile = ImageSerializer(required=False, read_only=True)

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
            'created_at',
            'pet_profile',
            'pet_profile_attachment_key'
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
    pet_profile = ImageSerializer(required=False)
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
            'pet_profile',
            'pet_profile_attachment_key'
        )
        read_only_fields = ('id', 'owner', 'created_at')
        depth = 2
