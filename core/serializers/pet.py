from rest_framework import serializers

from core.models import ClientProfile, Pet
from uploader.models import Image
from uploader.serializers import ImageSerializer


class PetSerializer(serializers.ModelSerializer):
    pet_picture = serializers.SerializerMethodField()

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
            'created_at',
            'pet_picture',
        )
        read_only_fields = ('id', 'owner', 'created_at')

    def create(self, validated_data):
        user = self.context['request'].user

        try:
            validated_data['owner'] = user.client_profile
        except ClientProfile.DoesNotExist:
            raise serializers.ValidationError('Usuário não possui perfil de Cliente')

        return super().create(validated_data)

    def get_pet_picture(self, obj):
        if not obj.pet_picture:
            return None

        return obj.pet_picture.url


class PetRegisterUpdateSerializer(serializers.ModelSerializer):
    pet_picture = serializers.SlugRelatedField(
        queryset=Image.objects.all(),
        slug_field='attachment_key',
        required=False,
        write_only=True,
    )

    class Meta:
        model = Pet
        fields = ('pet_picture', 'name', 'breed', 'size', 'weight', 'notes')


class PetDetailSerializer(serializers.ModelSerializer):
    pet_picture = ImageSerializer(required=False)

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
            'created_at',
            'pet_picture',
        )
        read_only_fields = ('id', 'owner', 'created_at')
        depth = 2
