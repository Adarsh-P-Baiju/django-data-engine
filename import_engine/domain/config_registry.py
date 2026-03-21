class BaseImportConfig:
    """
    Base configuration class for imports. Should be subclassed and registered.
    """
    model = None
    fields = {}

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
    Retrieve an activated configuration from the registry.
    """
    return _import_registry.get(name)
