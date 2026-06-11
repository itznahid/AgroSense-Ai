import os
import importlib.util
from pathlib import Path

# ── Base ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-vv$r&cwmt@nk_pr$b$z-vs%8owl+a!q*7-)wx15hz$e7ancyt_"
)

DEBUG = os.getenv("DEBUG", "True") == "True"
import os

ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,.up.railway.app"
).split(",")

CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "https://agrosense-ai-production-0073.up.railway.app"
).split(",")
# ── Applications ──────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # ── Core apps ────────────────────────────────────────────────────────────
    "accounts",
    "marketplace",
    "orders",
    "chatbot",
    "crop_disease",
    "recommend",

    # ── Enterprise AI layer ───────────────────────────────────────────────────
    "ai_engine",
    "ai_admin",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "CropReco.urls"

TEMPLATES = [
    {
        "BACKEND":  "django.template.backends.django.DjangoTemplates",
        "DIRS":     [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "CropReco.wsgi.application"

# ── Database ──────────────────────────────────────────────────────────────────
import dj_database_url

DATABASES = {
    "default": dj_database_url.config(
        default="sqlite:///db.sqlite3"
    )
}
# For production, switch to PostgreSQL:
# DATABASES = {
#     "default": {
#         "ENGINE":   "django.db.backends.postgresql",
#         "NAME":     os.environ.get("DB_NAME", "agrosense"),
#         "USER":     os.environ.get("DB_USER", "postgres"),
#         "PASSWORD": os.environ.get("DB_PASSWORD", ""),
#         "HOST":     os.environ.get("DB_HOST", "localhost"),
#         "PORT":     os.environ.get("DB_PORT", "5432"),
#     }
# }

# ── Password validation ───────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internationalisation ──────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE     = "Asia/Dhaka"
USE_I18N      = True
USE_TZ        = True

# ── Static & Media ────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Authentication ────────────────────────────────────────────────────────────
LOGIN_URL          = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ── Session ───────────────────────────────────────────────────────────────────
SESSION_COOKIE_AGE    = 86400 * 30  # 30 days
SESSION_SAVE_EVERY_REQUEST = False

# ═══════════════════════════════════════════════════════════════════════════════
# GEMINI MULTI-KEY CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
#
# Priority order: KEY_1 (Primary) → KEY_2 (Secondary) → KEY_3 (Emergency Backup)
# Keys can ALSO be managed via the AI Admin dashboard (database-backed).
# DB keys take priority over these settings when both are configured.
#
# Auto-failover triggers: 429, 500, 502, 503, 504, timeout, quota exhausted
# Model fallback: gemini-2.5-flash → gemini-2.0-flash → gemini-1.5-flash
#
GEMINI_API_KEY_1 = os.environ.get("GEMINI_API_KEY_1", "")   # Primary
GEMINI_API_KEY_2 = os.environ.get("GEMINI_API_KEY_2", "")   # Secondary
GEMINI_API_KEY_3 = os.environ.get("GEMINI_API_KEY_3", "")   # Emergency Backup

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY_1)

# ── Weather API (optional) ────────────────────────────────────────────────────
WEATHER_API_KEY  = os.environ.get("WEATHER_API_KEY", "")
WEATHER_API_BASE = "https://api.weatherapi.com/v1/current.json"

# ── AI Call Log Retention ─────────────────────────────────────────────────────
AI_CALL_LOG_RETENTION_DAYS = int(os.environ.get("AI_CALL_LOG_RETENTION_DAYS", 30))

# ── Cache disabled for SQLite-only MVP deployment ─────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    "version":            1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class":     "logging.StreamHandler",
            "formatter": "standard",
        },
        "file": {
            "class":     "logging.handlers.RotatingFileHandler",
            "filename":  BASE_DIR / "logs" / "agrosense.log",
            "maxBytes":  10 * 1024 * 1024,  # 10 MB
            "backupCount": 3,
            "formatter": "standard",
        },
    },
    "loggers": {
        "ai_engine":   {"handlers": ["console", "file"], "level": "INFO",    "propagate": False},
        "ai_admin":    {"handlers": ["console", "file"], "level": "INFO",    "propagate": False},
        "chatbot":     {"handlers": ["console"],          "level": "WARNING", "propagate": False},
        "crop_disease": {"handlers": ["console"],         "level": "WARNING", "propagate": False},
        "django":      {"handlers": ["console"],          "level": "WARNING", "propagate": False},
    },
}

# Create logs directory
os.makedirs(BASE_DIR / "logs", exist_ok=True)
