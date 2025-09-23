# settings.py
from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "dev-unsafe")
DEBUG = os.getenv("DEBUG", "0") == "1"

# Render external hostname (auto-provided at runtime)
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()

# Hosts / CSRF
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)

# If you add a custom domain later, add it here or via env:
# ALLOWED_HOSTS += ["api.yourdomain.com"]

CSRF_TRUSTED_ORIGINS = []
if RENDER_HOST:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_HOST}")
# If you add a custom domain:
# CSRF_TRUSTED_ORIGINS.append("https://api.yourdomain.com")

# ---------------------------------------------------------------------
# Apps / Middleware
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "portfolio",
    "rest_framework",
    "corsheaders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",   # serve static files
    "corsheaders.middleware.CorsMiddleware",        # CORS early in stack
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "backend.urls"   # change if your project module differs

TEMPLATES = [  # REQUIRED for admin (fixes admin.E403)
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],   # optional folder for your templates
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "backend.wsgi.application"  # change if needed

# ---------------------------------------------------------------------
# Database (Postgres on Render via DATABASE_URL; SQLite locally)
# ---------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------
# Static / Media
# ---------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# NOTE: For persistent uploads in production, use S3/R2 + django-storages.

# ---------------------------------------------------------------------
# CORS (set your frontend origins)
# ---------------------------------------------------------------------
# Prefer env to avoid hardcoding; comma-separated list like:
# FRONTEND_ORIGINS="https://<your-username>.github.io,https://portfolio.yourdomain.com"
_frontend_origins = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o.strip()]
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://192.168.0.36:3000",
    *(_frontend_origins or []),
]
# If you need cookies/auth across domains:
# CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------
# Internationalization / Defaults
# ---------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------
# Production security
# ---------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Enable HSTS once your domain is stable & HTTPS-only:
    # SECURE_HSTS_SECONDS = 3600
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_PRELOAD = True
