import re
from django.core.exceptions import ValidationError


class DSLValidator:
    def __init__(self, rules: list[str] | dict):
        self.rules = rules if isinstance(rules, list) else [rules]

    def validate(self, value):
        for rule in self.rules:
            if rule == "required" and not value:
                raise ValidationError("This field is required.")
            if not value:
                continue

            if rule == "email":
                if not re.match(r"[^@]+@[^@]+\.[^@]+", str(value)):
                    raise ValidationError("Invalid email address.")

            if rule == "phone":
                if not re.match(r"^\+?[0-9\s\-\(\).]{7,20}$", str(value)):
                    raise ValidationError("Invalid phone number format.")

            if rule.startswith("min:"):
                min_val = float(rule.split(":")[1])
                if float(value) < min_val:
                    raise ValidationError(f"Value must be at least {min_val}.")

            if rule.startswith("max:"):
                max_val = float(rule.split(":")[1])
                if float(value) > max_val:
                    raise ValidationError(f"Value must be at most {max_val}.")

        return value


def validate_row(config, row_data: dict) -> tuple[dict, dict]:
    cleaned = {}
    errors = {}

    for f_name, f_config in config.fields.items():
        val = row_data.get(f_name)

        if isinstance(f_config, list):
            rules = f_config
        elif isinstance(f_config, dict):
            rules = f_config.get("rules", [])
            if f_config.get("required") and "required" not in rules:
                rules.insert(0, "required")
        else:
            rules = []

        validator = DSLValidator(rules)
        try:
            cleaned[f_name] = validator.validate(val)
        except ValidationError as e:
            errors[f_name] = e.messages[0]

    return cleaned, errors
