from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import ClientProfile, ProviderProfile
from core.serializers import ClientSerializer, ProviderSerializer


class GlobalSearchView(APIView):

    def get(self, request):
        query = request.query_params.get('q')

        if not query:
            return Response({
                'providers': [],
                'clients': []
            })

        providers = ProviderProfile.objects.filter(
            Q(user__full_name__icontains=query) |
            Q(description__icontains=query) |
            Q(service_type__name__icontains=query)
        )

        clients = ClientProfile.objects.filter(
            Q(user__full_name__icontains=query)
        )

        return Response({
            'providers': ProviderSerializer(providers, many=True).data,
            'clients': ClientSerializer(clients, many=True).data
        })
