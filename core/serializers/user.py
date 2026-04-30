from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, SlugRelatedField

from core.models import User
from uploader.models import Image
from uploader.serializers import ImageSerializer


class UserSerializer(ModelSerializer):
    profile_picture_attachment_key = SlugRelatedField(
        source='profile_picture',
        queryset=Image.objects.all(),
        slug_field='attachment_key',
        required=False,
        write_only=True,
    )
    profile_picture = ImageSerializer(required=False, read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'provider_profile',
            'client_profile',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login',
            'groups',
            'profile_picture',
            'profile_picture_attachment_key'
        ]


class UserRegistrationSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'email', 'cpf', 'phone', 'full_name', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'provider_profile',
            'client_profile',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login',
            'groups',
        ]
        depth = 1
