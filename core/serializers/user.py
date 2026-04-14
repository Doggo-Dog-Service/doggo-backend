from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from core.models import User


class UserSerializer(ModelSerializer):
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
