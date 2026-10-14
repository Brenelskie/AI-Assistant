import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

PRODUCTION = os.getenv("DJANGO_ENV", "development").strip().lower() == "production"
DEBUG = not PRODUCTION
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if PRODUCTION and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("django-insecure")):
    raise ImproperlyConfigured("Production requires a private Django secret of at least 50 characters.")
if not SECRET_KEY:
    SECRET_KEY = "django-insecure-local-ai-assistant-change-for-production"

ALLOWED_HOSTS = [
    host.strip() for host in os.getenv(
        "DJANGO_ALLOWED_HOSTS", "" if PRODUCTION else "127.0.0.1,localhost,testserver"
    ).split(",") if host.strip()
]
if PRODUCTION and not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS before deploying.")
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

INSTALLED_APPS = ["django.contrib.staticfiles", "assistant"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {}
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
MAX_PROMPT_LENGTH = 4000
DATA_UPLOAD_MAX_MEMORY_SIZE = 32 * 1024
CSRF_FAILURE_VIEW = "assistant.views.csrf_failure"
CSRF_COOKIE_SECURE = PRODUCTION
SECURE_SSL_REDIRECT = PRODUCTION
if os.getenv("DJANGO_BEHIND_HTTPS_PROXY", "False").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
