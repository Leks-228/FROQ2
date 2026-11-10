import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


# =========================
# SECURITY
# =========================

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-key-change-me")

# Локально по умолчанию DEBUG=True (иначе без collectstatic падает админка).
# На продакшене DEBUG явно выключается переменной окружения: DEBUG=false.
DEBUG = os.environ.get("DEBUG", "True").lower() in ("1", "true", "yes")

# Список хостов можно задать через переменную окружения (через запятую).
# По умолчанию "*" — удобно локально; на реальном сервере лучше указать домен.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "*").split(",")
    if host.strip()
]

# Нужно только при работе через нестандартный домен/прокси.
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

# Render автоматически сообщает внешний домен сервиса в этой переменной.
# Добавляем его в ALLOWED_HOSTS и CSRF_TRUSTED_ORIGINS, чтобы формы
# (лайки, плейлисты, загрузка) работали без ручной настройки.
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    render_origin = f"https://{RENDER_EXTERNAL_HOSTNAME}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

if not DEBUG:
    # На проде сайт отдаётся по HTTPS (Render терминирует TLS),
    # поэтому куки должны передаваться только по HTTPS.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HSTS по умолчанию выключен: включать только когда домен окончательно
    # настроен (SECURE_HSTS_SECONDS=31536000 в переменных окружения).
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "").lower() in (
        "1", "true", "yes",
    )


# =========================
# APPS
# =========================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'main',

    'crispy_forms',
    'crispy_bootstrap5',

    'cloudinary',
    'cloudinary_storage',
]


# =========================
# MIDDLEWARE
# =========================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'music_site.urls'


# =========================
# TEMPLATES
# =========================

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


WSGI_APPLICATION = 'music_site.wsgi.application'


# =========================
# DATABASE (Railway)
# =========================

DATABASE_URL = os.environ.get('DATABASE_URL', '')

DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',   # запасной вариант для локальной разработки
        conn_max_age=600,
        # Neon «засыпает» при простое — проверяем соединение перед запросом,
        # иначе первый запрос после паузы может упасть.
        conn_health_checks=True,
        # SSL нужен только для облачной PostgreSQL (Neon и т.п.),
        # для SQLite этот параметр недопустим.
        ssl_require=DATABASE_URL.startswith(('postgres://', 'postgresql://')),
    )
}

# =========================
# PASSWORD VALIDATION
# =========================

# Страница входа для @login_required (по умолчанию Django ищет /accounts/login/).
LOGIN_URL = 'login'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# =========================
# INTERNATIONALIZATION
# =========================

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True


# =========================
# MEDIA / CLOUDINARY
# =========================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": os.environ.get("CLOUDINARY_API_KEY"),
    "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET"),
}

# Cloudinary используем только если заданы все три переменные окружения.
# Иначе (локальная разработка) файлы сохраняются в MEDIA_ROOT.
USE_CLOUDINARY = all(CLOUDINARY_STORAGE.values())


# =========================
# STORAGES
# =========================

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STORAGES = {
    "default": {
        "BACKEND": (
            "music_site.storage.SmartCloudinaryStorage"
            if USE_CLOUDINARY
            else "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        # Не падает с 500, если collectstatic не запускали (см. music_site/storage.py)
        "BACKEND": "music_site.storage.LenientCompressedManifestStaticFilesStorage",
    },
}


# =========================
# CRISPY FORMS
# =========================

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# =========================
# DEFAULT AUTO FIELD
# =========================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
