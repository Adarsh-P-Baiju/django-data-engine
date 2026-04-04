from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ImportEngineConfig(AppConfig):
    name = "import_engine"
    verbose_name = _("Django Data Import Engine")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """
        Perform app-specific initialization and checks.
        """
        try:
            from . import conf
        except ImportError:
            pass
