from rest_framework import serializers

from uploader.helpers.files import CONTENT_TYPE_JPG, CONTENT_TYPE_PDF, CONTENT_TYPE_PNG, get_content_type
from uploader.models import Document

# Documento de identidade do passeador: foto (celular) ou PDF escaneado.
VALID_DOCUMENT_TYPES = (CONTENT_TYPE_PDF, CONTENT_TYPE_JPG, CONTENT_TYPE_PNG)
MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024


class DocumentUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["attachment_key", "file", "description", "uploaded_on"]
        read_only_fields = ["attachment_key", "uploaded_on"]
        extra_kwargs = {"file": {"write_only": True}}

    def validate_file(self, value):
        if value.size > MAX_DOCUMENT_SIZE_BYTES:
            raise serializers.ValidationError('O documento deve ter no máximo 10 MB.')
        if get_content_type(value) not in VALID_DOCUMENT_TYPES:
            raise serializers.ValidationError('Envie o documento em PDF, JPEG ou PNG.')
        return value


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["url", "description", "uploaded_on", "attachment_key", "public_id"]
        read_only_fields = ["url", "attachment_key", "uploaded_on"]

    def create(self, validated_data):
        raise NotImplementedError("Use DocumentUploadSerializer to create document files.")
