import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from app.env import (
    DEFAULT_ALLOWED_HOSTS,
    DEFAULT_FRONTEND_ORIGINS,
    LAN_FRONTEND_ORIGIN,
    env_bool,
    env_list,
    with_dev_ip,
)

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Define o modo de execução da aplicação
MODE = os.getenv('MODE')

# Constrói o caminho base do projeto, usado para definir caminhos relativos
BASE_DIR = Path(__file__).resolve().parent.parent

# Segurança e configuração básica
DEBUG = env_bool('DEBUG', False)

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Defina SECRET_KEY no ambiente.')
    SECRET_KEY = 'django-insecure-dev-only'

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', DEFAULT_ALLOWED_HOSTS)
CORS_ALLOWED_ORIGINS = env_list('CORS_ALLOWED_ORIGINS', DEFAULT_FRONTEND_ORIGINS)
CSRF_TRUSTED_ORIGINS = env_list(
    'CSRF_TRUSTED_ORIGINS',
    DEFAULT_FRONTEND_ORIGINS + ['https://doggo-backend.class.fabricadesoftware.ifc.edu.br'],
)

# IP do computador na rede local (gravado no .env por `pdm dev`): só em DEBUG, para abrir o frontend pelo celular
MY_IP = os.getenv('MY_IP')
ALLOWED_HOSTS = with_dev_ip(ALLOWED_HOSTS, MY_IP, debug=DEBUG)
CORS_ALLOWED_ORIGINS = with_dev_ip(CORS_ALLOWED_ORIGINS, MY_IP, debug=DEBUG, template=LAN_FRONTEND_ORIGIN)
CSRF_TRUSTED_ORIGINS = with_dev_ip(CSRF_TRUSTED_ORIGINS, MY_IP, debug=DEBUG, template=LAN_FRONTEND_ORIGIN)

if not DEBUG:
    # Em produção o TLS termina no proxy reverso, que informa o esquema original pelo cabeçalho X-Forwarded-Proto
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Aplicações instaladas
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'cloudinary_storage',
    'cloudinary',
    'corsheaders',
    'channels',
    'django_extensions',
    'django_filters',
    'drf_spectacular',
    'rest_framework',
    'uploader',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'app.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'app.wsgi.application'
ASGI_APPLICATION = 'app.asgi.application'

# Configuração do Redis / Django Channels
REDIS_URL = os.getenv(
    'REDIS_URL',
    'redis://127.0.0.1:6379',
)

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [
                {
                    'address': REDIS_URL,
                    'socket_timeout': None,
                }
            ]
        }
    }
}

# Banco de dados
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=0,
        conn_health_checks=True,
    )
}

# Validação de senhas
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Configurações de internacionalização
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# Configurações de arquivos estáticos
STATIC_URL = 'static/'

# Configurações de arquivos de mídia (App Uploader)
MEDIA_ENDPOINT = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')
FILE_UPLOAD_PERMISSIONS = 0o640

# Configurações específicas para desenvolvimento, migração e produção
if MODE == 'DEVELOPMENT':
    MEDIA_URL = 'http://127.0.0.1:8000/media/'
else:
    MEDIA_URL = '/media/'
    CLOUDINARY_URL = os.getenv('CLOUDINARY_URL')
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
    STORAGES = {
        'default': {
            'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

# Tipo padrão de campo para chaves primárias
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configurações do DRF e drf-spectacular (OpenAPI/Swagger)
SPECTACULAR_SETTINGS = {
    'TITLE': 'DOGGO API',
    'DESCRIPTION': 'API da plataforma DOGGO — Dog Services.',
    'VERSION': '1.0.0',
}

# Modelo de usuário personalizado
AUTH_USER_MODEL = 'core.User'

# Limite de requisições dos endpoints de autenticação (escopo 'auth' do throttle)
AUTH_THROTTLE_RATE = os.getenv('AUTH_THROTTLE_RATE', '10/min')

# Quantos proxies reversos ficam na frente da aplicação. O DRF usa isso para achar o IP real do cliente em
# X-Forwarded-For; sem o valor, o cabeçalho inteiro (forjável) vira a identidade do throttle.
NUM_PROXIES = int(os.getenv('NUM_PROXIES', '0' if DEBUG else '1'))

# Configurações do Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework_simplejwt.authentication.JWTAuthentication',),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'DEFAULT_PAGINATION_CLASS': 'app.pagination.CustomPagination',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'PAGE_SIZE': 10,
    'DEFAULT_THROTTLE_RATES': {'auth': AUTH_THROTTLE_RATE},
    'NUM_PROXIES': NUM_PROXIES,
}

# Configurações do Simple JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=180),  # Tokens de acesso expiram em 3 horas
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),  # Tokens de atualização expiram em 1 dia
    'AUTH_HEADER_TYPES': ('Bearer',),
}
