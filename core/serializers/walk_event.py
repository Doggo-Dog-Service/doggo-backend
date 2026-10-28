from rest_framework import serializers

from core.models import WalkEvent
from uploader.models import Image

NOTE_MAX_LENGTH = 1000
MAX_LATITUDE = 90
MAX_LONGITUDE = 180


class WalkEventSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = WalkEvent
        fields = ('id', 'kind', 'latitude', 'longitude', 'image_url', 'created_at')

    def get_image_url(self, obj) -> str | None:
        return obj.image.url if obj.image_id else None


class WalkEventCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=WalkEvent.Kind.choices)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    image_attachment_key = serializers.SlugRelatedField(
        slug_field='attachment_key', queryset=Image.objects.all(), required=False, allow_null=True
    )

    def validate_latitude(self, value):
        if value is not None and not -MAX_LATITUDE <= value <= MAX_LATITUDE:
            raise serializers.ValidationError('Latitude inválida.')
        return value

    def validate_longitude(self, value):
        if value is not None and not -MAX_LONGITUDE <= value <= MAX_LONGITUDE:
            raise serializers.ValidationError('Longitude inválida.')
        return value

    def validate(self, attrs):
        if (attrs.get('latitude') is None) != (attrs.get('longitude') is None):
            raise serializers.ValidationError('Informe latitude e longitude juntas.')
        if attrs['kind'] == WalkEvent.Kind.PHOTO:
            if attrs.get('image_attachment_key') is None:
                raise serializers.ValidationError({'image_attachment_key': 'Envie a foto.'})
        else:
            attrs['image_attachment_key'] = None
        return attrs


class ServiceNoteSerializer(serializers.Serializer):
    provider_note = serializers.CharField(max_length=NOTE_MAX_LENGTH, allow_blank=True)
