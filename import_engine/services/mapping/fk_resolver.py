import logging
from collections import defaultdict
from typing import Dict, List, Any, Optional
from django.db import transaction, models
from import_engine.domain.config_registry import get_config

logger = logging.getLogger("import_engine.metrics")

class FKResolver:
    """
    Advanced Foreign Key Resolver with multi-stage prefetching, 
    atomic auto-creation, and optimized local caching.
    """
    def __init__(self, config):
        self.config = config
        self.fk_fields = {
            f_name: f_config
            for f_name, f_config in config.fields.items()
            if isinstance(f_config, dict) and "fk" in f_config
        }
        # Local identity maps: field_name -> lookup_value -> instance
        self._cache: Dict[str, Dict[Any, models.Model]] = defaultdict(dict)

    def prefetch(self, rows_data: List[Dict[str, Any]]):
        """
        Processes a batch of rows to resolve all foreign keys in minimal queries.
        Supports automatic creation for missing records if configured.
        """
        for f_name, f_config in self.fk_fields.items():
            fk_name = f_config.get("fk")
            fk_reg_config = get_config(fk_name)
            
            if not fk_reg_config:
                logger.warning(f"FKResolver: No config found for registered FK '{fk_name}'")
                continue
                
            model = fk_reg_config.model
            lookup_field = getattr(fk_reg_config, "lookup_field", f_config.get("lookup", "name"))
            
            # 1. Identify distinct values needed
            values_needed = {row.get(f_name) for row in rows_data if row.get(f_name)}
            if not values_needed:
                continue
            
            # 2. Bulk Fetch Existing Refs
            existing_objs = model.objects.filter(
                **{f"{lookup_field}__in": values_needed}
            ).only("id", lookup_field)
            
            for obj in existing_objs:
                val = getattr(obj, lookup_field)
                self._cache[f_name][val] = obj

            # 3. Handle Auto-Creation for Missing Values
            if f_config.get("create_if_missing"):
                missing_values = values_needed - set(self._cache[f_name].keys())
                if missing_values:
                    self._handle_missing_creation(f_name, model, lookup_field, missing_values, f_config)

    def _handle_missing_creation(self, f_name, model, lookup_field, missing_values, f_config):
        """Atomically creates missing records and updates the cache."""
        defaults = f_config.get("defaults", {})
        new_objs = []
        for val in missing_values:
            kwargs = {lookup_field: val, **defaults}
            # Auto-generate 'code' if model has it and not provided
            if "code" not in kwargs and hasattr(model, "code"):
                kwargs["code"] = str(val)[:10].upper()
            new_objs.append(model(**kwargs))

        try:
            with transaction.atomic():
                # use ignore_conflicts to handle race conditions where another worker created it
                model.objects.bulk_create(new_objs, ignore_conflicts=True)
                
                # Re-query inside the transaction to ensure we get the IDs for our cache
                created_objs = model.objects.filter(
                    **{f"{lookup_field}__in": missing_values}
                ).only("id", lookup_field)
                
                for obj in created_objs:
                    val = getattr(obj, lookup_field)
                    self._cache[f_name][val] = obj
                    
        except Exception as e:
            logger.error({
                "event": "fk_auto_create_failed",
                "model": model.__name__,
                "field": f_name,
                "error": str(e)
            })

    def resolve(self, f_name: str, value: Any) -> Optional[models.Model]:
        """Returns the resolved instance from the local cache."""
        return self._cache.get(f_name, {}).get(value)

    def clear(self):
        """Clears the local prefetch cache."""
        self._cache.clear()
