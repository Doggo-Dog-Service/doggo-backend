from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsProviderAvailabilityOwnerOrReadOnly(BasePermission):
    """Permite leitura a qualquer autenticado; escrita apenas ao provider dono."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return (
            hasattr(request.user, 'provider_profile')
            and obj.provider.user == request.user
        )
