from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import ProviderProfile
from core.serializers import ProviderSerializer


class GlobalSearchView(APIView):

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
