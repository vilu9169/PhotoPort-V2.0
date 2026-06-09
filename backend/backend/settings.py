# settings.py
from pathlib import Path
import os
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env file

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------
DEBUG = os.getenv("DEBUG", "0") == "1"
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-unsafe-key"
    else:
        raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG is disabled.")

# Render external hostname (auto-provided at runtime)
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
ADMIN_PATH = os.getenv("ADMIN_PATH", "admin").strip("/")
if not ADMIN_PATH:
    raise ImproperlyConfigured("ADMIN_PATH cannot be empty.")

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)
# If you add a custom domain later, add it here or via env:
# ALLOWED_HOSTS += ["api.yourdomain.com"]

CSRF_TRUSTED_ORIGINS = []
if RENDER_HOST:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_HOST}")
# CSRF_TRUSTED_ORIGINS += ["https://api.yourdomain.com"]

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

CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "").strip()
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()
USE_CLOUDINARY = bool(CLOUDINARY_URL or CLOUDINARY_CLOUD_NAME)

if USE_CLOUDINARY and not CLOUDINARY_URL:
    missing_cloudinary_settings = [
        name
        for name, value in (
            ("CLOUDINARY_CLOUD_NAME", CLOUDINARY_CLOUD_NAME),
            ("CLOUDINARY_API_KEY", CLOUDINARY_API_KEY),
            ("CLOUDINARY_API_SECRET", CLOUDINARY_API_SECRET),
        )
        if not value
    ]
    if missing_cloudinary_settings:
        raise ImproperlyConfigured(
            "Cloudinary is partially configured. Missing: "
            + ", ".join(missing_cloudinary_settings)
        )

if USE_CLOUDINARY:
    INSTALLED_APPS += ["cloudinary_storage", "cloudinary"]

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

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],   # optional
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

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ---------------------------------------------------------------------
# Database (Postgres on Render via DATABASE_URL; SQLite locally)
# ---------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if RENDER_HOST and not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL must be set on Render.")

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
MEDIA_ROOT = BASE_DIR / "media"

USE_S3 = bool(os.getenv("AWS_STORAGE_BUCKET_NAME"))

if USE_CLOUDINARY:
    # ---- Cloudinary for media, WhiteNoise for static ----
    STORAGES = {
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    if not CLOUDINARY_URL:
        CLOUDINARY_STORAGE = {
            "CLOUD_NAME": CLOUDINARY_CLOUD_NAME,
            "API_KEY": CLOUDINARY_API_KEY,
            "API_SECRET": CLOUDINARY_API_SECRET,
            "SECURE": True,
        }
    MEDIA_URL = "/media/"
elif USE_S3:
    # ---- S3 for media, WhiteNoise for static ----
    STORAGES = {
        "default": {  # media files (uploads)
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {  # collected static files
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "eu-north-1")
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")  # leave empty for AWS S3
    AWS_DEFAULT_ACL = None
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=31536000, public"}
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_CUSTOM_DOMAIN = os.getenv("AWS_S3_CUSTOM_DOMAIN")  # e.g. cdn.example.com

    if AWS_S3_CUSTOM_DOMAIN:
        MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"
    elif AWS_S3_ENDPOINT_URL:
        MEDIA_URL = f"{AWS_S3_ENDPOINT_URL.rstrip('/')}/{AWS_STORAGE_BUCKET_NAME}/"
    else:
        MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/"

else:
    # ---- Local disk for media (dev) + WhiteNoise for static ----
    STORAGES = {
        "default": {  # media files (uploads)
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    MEDIA_URL = "/media/"

# Reject unexpectedly large requests before application code handles them.
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 1
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

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
# CORS_ALLOW_CREDENTIALS = True  # enable only if you need cookies/auth

REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("API_ANON_RATE", "120/minute"),
        "user": os.getenv("API_USER_RATE", "600/minute"),
    },
}

# ---------------------------------------------------------------------
# Internationalization / Defaults
# ---------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------
# Production security
# ---------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_AGE = 60 * 60 * 8
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
