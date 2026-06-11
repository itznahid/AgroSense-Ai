"""ai_engine Django app config."""
from django.apps import AppConfig


class AiEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_engine"
    verbose_name = "AgroSense AI Engine"

    def ready(self):
        # Ensure digital twins exist for all existing users on startup (lazy).
        pass
