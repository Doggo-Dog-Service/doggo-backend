from rest_framework import serializers

from uploader.helpers.files import CONTENT_TYPE_JPG, CONTENT_TYPE_PNG, get_content_type
from uploader.models import Image

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024


class ImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = ["attachment_key", "file", "description", "uploaded_on", "url"]
        read_only_fields = ["attachment_key", "uploaded_on", "url"]
        extra_kwargs = {"file": {"write_only": True}}

    def validate_file(self, value):
        if value.size > MAX_IMAGE_SIZE_BYTES:
            raise serializers.ValidationError('A imagem deve ter no máximo 5 MB.')

        # O tipo vem do conteúdo (python-magic), não do cabeçalho enviado pelo cliente.
        if get_content_type(value) not in {CONTENT_TYPE_JPG, CONTENT_TYPE_PNG}:
            raise serializers.ValidationError('Envie uma imagem JPEG ou PNG.')
        return value


class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = ["url", "description", "uploaded_on"]
        read_only_fields = ["url", "attachment_key", "uploaded_on"]

    def create(self, validated_data):
        raise NotImplementedError("Use ImageUploadSerializer to create images.")
