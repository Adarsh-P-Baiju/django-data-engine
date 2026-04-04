from django.conf import settings
from django.core.signals import setting_changed

class ImportEngineSettings:
    """
    A settings object that allows import_engine settings to be accessed
    as properties. For example:
        from import_engine.conf import import_engine_settings
        print(import_engine_settings.MAX_FILE_SIZE_MB)
    """

    prefix = "IMPORT_ENGINE_"

    defaults = {
        "MAX_FILE_SIZE_MB": 1024,
        "STAGING_PATH_PREFIX": "imports/pending/",
        "CLAMAV_HOST": "localhost",
        "CLAMAV_PORT": 3310,
        "CLAMAV_FAIL_SAFE": True,
        "REGION_QUEUES": {
            "DEFAULT": "heavy_tasks",
        },
        "THROTTLE_RATES": {
            "import_uploads": "100/day",
            "import_uploads_anon": "10/day",
        },
    }

    def __init__(self):
        self._cache = {}

    def __getattr__(self, name):
        if name not in self.defaults:
            raise AttributeError(f"Invalid setting: '{name}'")

        if name not in self._cache:
            val = getattr(settings, self.prefix + name, self.defaults[name])
            self._cache[name] = val

        return self._cache[name]

    def reload(self):
        self._cache = {}

import_engine_settings = ImportEngineSettings()

def reload_import_engine_settings(*args, **kwargs):
    setting = kwargs.get("setting")
    if setting and setting.startswith(import_engine_settings.prefix):
        import_engine_settings.reload()

setting_changed.connect(reload_import_engine_settings)
