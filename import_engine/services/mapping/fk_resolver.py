from collections import defaultdict

class FKResolver:
    def __init__(self, config):
        self.config = config
        self.fk_fields = {
            f_name: f_config for f_name, f_config in config.fields.items() 
            if isinstance(f_config, dict) and f_config.get("type") == "fk"
        }
        self.lookups = defaultdict(dict)
        self.reverse_lookups = defaultdict(dict)
        
    def prefetch(self, rows_data: list[dict]):
        for f_name, f_config in self.fk_fields.items():
            model = f_config['model']
            lookup_field = f_config.get('lookup', 'name')
            
            values_needed = {row.get(f_name) for row in rows_data if row.get(f_name)}
            if not values_needed:
                continue
                
            existing_objs = model.objects.filter(**{f"{lookup_field}__in": values_needed}).values('id', lookup_field)
            
            for obj in existing_objs:
                val = obj[lookup_field]
                self.lookups[f_name][val] = obj['id']
                self.reverse_lookups[f_name][obj['id']] = val
                
            if f_config.get('create_if_missing'):
                missing_values = values_needed - set(self.lookups[f_name].keys())
                if missing_values:
                    new_objs = [model(**{lookup_field: val}) for val in missing_values]
                    model.objects.bulk_create(new_objs, ignore_conflicts=True)
                    
                    created_objs = model.objects.filter(**{f"{lookup_field}__in": missing_values}).values('id', lookup_field)
                    for obj in created_objs:
                        val = obj[lookup_field]
                        self.lookups[f_name][val] = obj['id']
                        self.reverse_lookups[f_name][obj['id']] = val

    def resolve(self, f_name, value):
        return self.lookups.get(f_name, {}).get(value)
