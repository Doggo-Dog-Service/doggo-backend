from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import ProviderProfile
from core.serializers import ProviderSerializer


class GlobalSearchView(APIView):

    @extend_schema(
        summary='Busca global',
        description=(
            'Busca prestadores por nome, descrição ou tipo de serviço. '
            '`clients` vem sempre vazio (mantido por compatibilidade): clientes não entram na busca.'
        ),
        parameters=[OpenApiParameter('q', str, required=False, description='Termo buscado.')],
        responses=inline_serializer(
            name='GlobalSearchResponse',
            fields={
                'providers': ProviderSerializer(many=True),
                'clients': serializers.ListField(child=serializers.DictField()),
            },
        ),
    )
    def get(self, request):
        query = request.query_params.get('q')

        if not query:
            return Response({
                'providers': [],
                'clients': []
            })

        providers = (
            ProviderProfile.objects.with_rating()
            .select_related('user__profile_picture', 'service_type')
            .filter(
                Q(user__full_name__icontains=query) |
                Q(description__icontains=query) |
                Q(service_type__name__icontains=query)
            )
        )

        # Clientes não entram na busca (dados pessoais e localização); a chave fica por compatibilidade.
        return Response({
            'providers': ProviderSerializer(providers, many=True).data,
            'clients': []
        })
