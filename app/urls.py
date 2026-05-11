from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from core.views import (
    ClientViewSet,
    GlobalSearchView,
    PetViewSet,
    ProfileView,
    ProviderViewSet,
    ServiceTypeViewSet,
    ServiceViewSet,
    UserRegistrationView,
    UserViewSet,
)
from core.views.payment import PaymentViewSet
from uploader.router import router as uploader_router

router = DefaultRouter()


router.register(r'clients', ClientViewSet, basename='clients')
router.register(r'pets', PetViewSet, basename='pets')
router.register(r'providers', ProviderViewSet, basename='providers')
router.register(r'services', ServiceViewSet, basename='services')
router.register(r'type-services', ServiceTypeViewSet, basename='type-services')
router.register(r'users', UserViewSet, basename='users')
router.register(r'payment', PaymentViewSet, basename='payment')


urlpatterns = [
    path('admin/', admin.site.urls),
    # Uploader
    path('api/media/', include(uploader_router.urls)),
    # OpenAPI 3
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'api/doc/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
    path(
        'api/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc',
    ),
    # Autenticação JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    # Registro de usuários
    path('api/register/', UserRegistrationView.as_view(), name='user_registration'),
    path('api/profile/', ProfileView.as_view(), name='user_profile'),
    # Busca
    path('api/search/', GlobalSearchView.as_view(), name='search'),
    # API
    path('api/', include(router.urls)),
]
urlpatterns += static(settings.MEDIA_ENDPOINT, document_root=settings.MEDIA_ROOT)
