from pathlib import Path
import os
from dotenv import load_dotenv
from datetime import timedelta
import dj_database_url

# Build paths first — before anything else
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / '.env')

# ===== SECURITY =====
SECRET_KEY = os.getenv('SECRET_KEY', 'fallback-secret-key')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
CAMERA_SECRET_KEY = os.getenv('CAMERA_SECRET_KEY')

ALLOWED_HOSTS = []

# ===== APPS =====
INSTALLED_APPS = [
    'corsheaders',  # ضيفيها هنا
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'parking',
    'accounts',
    'administration',
    'pgvector',
    'django_extensions',
]

# ===== MIDDLEWARE =====
MIDDLEWARE = [
  
    'corsheaders.middleware.CorsMiddleware',  # ← must be at the TOP
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
# to push this edit to git hub and test the database 
# git add .

WSGI_APPLICATION = 'core.wsgi.application'

# ===== DATABASE (single — reads from .env) =====
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600
    )
}

# ===== PASSWORD VALIDATION =====
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),   # 24 hours instead of 5 minutes
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# ===== REST FRAMEWORK =====
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',  # ← required for admin dashboard
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),

    
}

# ===== INTERNATIONALIZATION =====
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Cairo'
USE_I18N = True
USE_TZ = True

# ===== STATIC & MEDIA =====
STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760

DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000
# ===== CORS =====
CORS_ALLOW_ALL_ORIGINS = True
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  

DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000