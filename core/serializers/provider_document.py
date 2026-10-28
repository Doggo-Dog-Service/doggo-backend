from rest_framework import serializers

from core.models import ProviderDocument
from uploader.models import Document


class ProviderDocumentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProviderDocument
        fields = ('kind', 'url', 'created_at')

    def get_url(self, obj) -> str:
        return obj.document.url


class ProviderDocumentCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=ProviderDocument.Kind.choices)
    document_attachment_key = serializers.SlugRelatedField(slug_field='attachment_key', queryset=Document.objects.all())
