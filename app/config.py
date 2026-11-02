"""Application configuration for the Trekking Management Application (TMA)."""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "tma-dev-secret-change-me")

    # --- SQLite (mandatory DB) -------------------------------------------------
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "instance", "tma.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- JWT -------------------------------------------------------------------
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "12"))

    # --- Redis cache (mandatory) ----------------------------------------------
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "60"))
    CACHE_PREFIX = "tma"

    # --- Celery / Redis broker --------------------------------------------------
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)

    # --- Mail (monthly report / reminders) --------------------------------------
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "1025"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "false").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "tma-noreply@treks.local")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@trekking.local")

    # --- Google Chat webhook (daily reminders) ----------------------------------
    GCHAT_WEBHOOK_URL = os.environ.get("GCHAT_WEBHOOK_URL", "")

    # --- Pre-existing admin (created programmatically, no registration) --------
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    ADMIN_EMAIL_BOOTSTRAP = os.environ.get("ADMIN_EMAIL", "admin@trekking.local")

    JSON_SORT_KEYS = False


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    REDIS_URL = ""  # forces in-process fallback cache during tests
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
    WTF_CSRF_ENABLED = False
