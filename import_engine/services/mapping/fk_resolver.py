from collections import defaultdict


class FKResolver:
    def __init__(self, config):
        self.config = config
        self.fk_fields = {
            f_name: f_config
            for f_name, f_config in config.fields.items()
            if isinstance(f_config, dict) and "fk" in f_config
        }
        self.lookups = defaultdict(dict)
        self.reverse_lookups = defaultdict(dict)

    def prefetch(self, rows_data: list[dict]):
        from import_engine.domain.config_registry import (
            get_config as get_registry_config,
        )

        for f_name, f_config in self.fk_fields.items():
            fk_name = f_config.get("fk")
            fk_reg_config = get_registry_config(fk_name)
            model = fk_reg_config.model if fk_reg_config else None
            if not model:
                continue

            lookup_field = getattr(
                fk_reg_config, "lookup_field", f_config.get("lookup", "name")
            )

            values_needed = {row.get(f_name) for row in rows_data if row.get(f_name)}
            if not values_needed:
                continue

            existing_objs = model.objects.filter(
                **{f"{lookup_field}__in": values_needed}
            ).only("id", lookup_field)

            for obj in existing_objs:
                val = getattr(obj, lookup_field)
                self.lookups[f_name][val] = obj
                self.reverse_lookups[f_name][obj.id] = val

            if f_config.get("create_if_missing"):
                missing_values = values_needed - set(self.lookups[f_name].keys())
                if missing_values:
                    defaults = f_config.get("defaults", {})
                    new_objs = []
                    for val in missing_values:
                        kwargs = {lookup_field: val, **defaults}
                        # Auto-generate a generic code if missing for Department
                        if "code" not in kwargs and hasattr(model, "code"):
                            kwargs["code"] = val[:10].upper()
                        new_objs.append(model(**kwargs))

                    try:
                        model.objects.bulk_create(new_objs, ignore_conflicts=True)
                    except Exception as e:
                        import logging

                        logging.getLogger("import_engine.metrics").error(
                            f"Auto-create failed for {model.__name__}: {e}"
                        )

                    created_objs = model.objects.filter(
                        **{f"{lookup_field}__in": missing_values}
                    ).only("id", lookup_field)
                    for obj in created_objs:
                        val = getattr(obj, lookup_field)
                        self.lookups[f_name][val] = obj
                        self.reverse_lookups[f_name][obj.id] = val

    def resolve(self, f_name, value):
        return self.lookups.get(f_name, {}).get(value)
