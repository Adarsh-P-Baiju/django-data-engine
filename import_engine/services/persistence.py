def bulk_persist(model, instances: list, upsert_fields: dict = None):
    """
    Saves instances using bulk_create. 
    Can utilize upsert via PostgreSQL ON CONFLICT utilizing unique_fields and update_fields.
    """
    if upsert_fields:
        unique_fields = upsert_fields.get('unique_fields', [])
        update_fields = upsert_fields.get('update_fields', [])
        
        model.objects.bulk_create(
            instances,
            update_conflicts=True,
            unique_fields=unique_fields,
            update_fields=update_fields
        )
    else:
        model.objects.bulk_create(instances, ignore_conflicts=True)
