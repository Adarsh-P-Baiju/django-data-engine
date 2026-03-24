class BaseImportConfig:
    """
    Base configuration class for imports. Should be subclassed and registered.
    """

    model = None
    fields = {}
    conflict_resolution = "fail"
    upsert_keys = None

    def validate(self):
        """Perform basic validation on the configuration."""
        if not self.model:
            raise ValueError(f"Import config {self.__class__.__name__} is missing 'model'")
        if not self.fields:
            raise ValueError(f"Import config {self.__class__.__name__} is missing 'fields'")


_import_registry = {}


def register_import(name):
    """
    Decorator to register an import configuration under a specific model/name.
    """

    def decorator(cls):
        _import_registry[name] = cls
        return cls

    return decorator


def get_config(name):
    """
    Retrieve an instantiated configuration from the registry.
    """
    config_cls = _import_registry.get(name)
    if not config_cls:
        return None
    
    config = config_cls()
    config.validate()
    return config
