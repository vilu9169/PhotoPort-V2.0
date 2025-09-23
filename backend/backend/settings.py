# settings.py
from pathlib import Path
import os
import dj_database_url  # NEW

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "dev-unsafe")
DEBUG = os.getenv("DEBUG", "0") == "1"

# Allow localhost and the Render-hosted name
ALLOWED_HOSTS = [
    "localhost", "127.0.0.1",
    os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
]

# If you’ll put a custom domain on Render, add it too:
# ALLOWED_HOSTS += ["api.yourdomain.com"]

# Trust the Render URL (needed for CSRF on HTTPS)
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST:
    CSRF_TRUSTED_ORIGINS = [f"https://{RENDER_HOST}"]
else:
    CSRF_TRUSTED_ORIGINS = []

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'portfolio', 'rest_framework',
    'corsheaders',   # keep
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # NEW: serve static files
    'corsheaders.middleware.CorsMiddleware',        # keep high in stack
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ---- CORS ----
CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://192.168.0.36:3000",
    # Add your production frontend(s):
    "https://<your-username>.github.io",      # GitHub Pages
    # "https://portfolio.yourdomain.com",     # if using a custom domain
]

# ---- Database (use Postgres via DATABASE_URL on Render; fallback to SQLite locally) ----
DATABASE_URL = os.getenv("DATABASE_URL")
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

# ---- Static files via WhiteNoise ----
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"               # NEW
# Enable compressed, hashed static files
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---- Media (optional) ----
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# NOTE: Render’s filesystem is ephemeral. For user uploads in production,
# prefer S3/R2 + django-storages later.

# ---- Basic production security hardening (safe defaults) ----
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HSTS: enable once your domain is fully HTTPS and stable
    # SECURE_HSTS_SECONDS = 3600
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_PRELOAD = True
