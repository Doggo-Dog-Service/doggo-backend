import re

from django.contrib.auth import password_validation
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, SlugRelatedField

from core.models import User
from core.validators import is_valid_cpf
from uploader.models import Image
from uploader.serializers import ImageSerializer

CPF_MASKED_MAX_LENGTH = 14  # 000.000.000-00


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
            'phone',
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
        read_only_fields = [
            'email',
            'cpf',
            'is_active',
            'is_staff',
            'is_superuser',
            'groups',
            'last_login',
            'provider_profile',
            'client_profile',
        ]
        # O telefone é editável pelo dono, mas não aparece quando o usuário vem aninhado em outras respostas.
        extra_kwargs = {'phone': {'write_only': True}}


class UserRegistrationSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    # Aceita máscara na entrada; validate_cpf normaliza para só dígitos (o model guarda 11).
    cpf = serializers.CharField(max_length=CPF_MASKED_MAX_LENGTH)

    profile_picture = serializers.SlugRelatedField(
        queryset=Image.objects.all(),
        slug_field='attachment_key',
        required=False,
        write_only=True,
    )

    class Meta:
        model = User
        fields = ['id', 'profile_picture', 'email', 'cpf', 'phone', 'full_name', 'password']

    def validate_cpf(self, value):
        digits = re.sub(r'\D', '', value)
        if not is_valid_cpf(digits):
            raise serializers.ValidationError('CPF inválido.')
        return digits

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserProfileSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'full_name',
            'cpf',
            'phone',
            'provider_profile',
            'client_profile',
            'is_active',
            'is_staff',
            'is_superuser',
            'last_login',
            'groups',
            'profile_picture',
        ]
        depth = 1
