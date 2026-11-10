import os
import shutil
from pathlib import Path

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

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

if not DEBUG:
    # На PythonAnywhere сайт отдаётся по HTTPS (прокси терминирует TLS),
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
# DATA / DATABASE (SQLite)
# =========================

# Папка, в которой лежат база и загруженные файлы.
# На PythonAnywhere по умолчанию выносим её за пределы папки с кодом
# (/home/<username>/freq-data), чтобы обновление сайта не затрагивало
# треки, обложки и аккаунты. Локально данные остаются в папке проекта.
def _default_data_dir():
    if os.environ.get('PYTHONANYWHERE_DOMAIN'):
        return Path.home() / 'freq-data'
    return BASE_DIR


DATA_DIR = Path(os.environ.get('FREQ_DATA_DIR', str(_default_data_dir())))

# Один раз переносим уже существующие базу и media в постоянную папку.
# Копируем, а не перемещаем: старые файлы остаются как резервная копия.
if DATA_DIR != BASE_DIR:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        project_db = BASE_DIR / 'db.sqlite3'
        data_db = DATA_DIR / 'db.sqlite3'
        if project_db.is_file() and not data_db.exists():
            shutil.copy2(project_db, data_db)

        project_media = BASE_DIR / 'media'
        data_media = DATA_DIR / 'media'
        if project_media.is_dir() and not data_media.exists():
            shutil.copytree(project_media, data_media)
    except OSError:
        # Если постоянная папка недоступна, работаем как раньше — из проекта.
        DATA_DIR = BASE_DIR


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DB_PATH', str(DATA_DIR / 'db.sqlite3')),
    }
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
# MEDIA / STATIC
# =========================

MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', str(DATA_DIR / 'media')))

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
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
