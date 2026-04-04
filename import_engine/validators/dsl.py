import re
import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class DSLValidator:
    """
    Advanced, modular Validation DSL Engine.
    Supports atomic rules, parameterized rules, and row-aware cross-field validation.
    """

    def __init__(self, field_name: str, rules: List[str], config: Any):
        self.field_name = field_name
        self.rules = rules
        self.config = config

    def validate(self, value: Any, row_data: Dict[str, Any]) -> Any:
        """
        Executes all registered rules against the field value.
        Passes the entire row_data for cross-field context.
        """
        for rule_str in self.rules:

            if rule_str == "required" and (value is None or str(value).strip() == ""):
                raise ValidationError(f"Field '{self.field_name}' is required.")

            if value is None or str(value).strip() == "":
                continue


            parts = rule_str.split(":", 1)
            rule_name = parts[0]
            params = parts[1] if len(parts) > 1 else None


            handler = getattr(self, f"_rule_{rule_name}", None)
            if handler:
                handler(value, params, row_data)
            elif rule_name == "encrypt":

                from import_engine.services.encryption_service import EncryptionService

                value = EncryptionService.encrypt(value)
            else:

                self._handle_common_rules(rule_name, value)

        return value

    def _rule_min(self, value, params, row_data):
        if params and float(value) < float(params):
            raise ValidationError(f"Value must be at least {params}.")

    def _rule_max(self, value, params, row_data):
        if params and float(value) > float(params):
            raise ValidationError(f"Value must be at most {params}.")

    def _rule_regex(self, value, params, row_data):
        if params and not re.match(params, str(value)):
            raise ValidationError("Value does not match required pattern.")

    def _rule_in(self, value, params, row_data):
        if params:
            allowed = [v.strip() for v in params.split(",")]
            if str(value) not in allowed:
                raise ValidationError(f"Value must be one of: {params}")

    def _rule_after(self, value, params, row_data):
        """Cross-field date validation: current field must be after target field."""
        if not params:
            return
        other_val = row_data.get(params)
        if not other_val:
            return

        try:
            current_date = self._parse_date(value)
            other_date = self._parse_date(other_val)
            if current_date <= other_date:
                raise ValidationError(f"Must be after {params} ({other_val})")
        except (ValueError, TypeError):
            pass

    def _handle_common_rules(self, rule_name, value):
        if rule_name == "email":
            if not re.match(r"[^@]+@[^@]+\.[^@]+", str(value)):
                raise ValidationError("Invalid email address.")
        elif rule_name == "phone":
            if not re.match(r"^\+?[0-9\s\-\(\).]{7,20}$", str(value)):
                raise ValidationError("Invalid phone number format.")
        elif rule_name == "date":
            self._parse_date(value)

    def _parse_date(self, value):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(str(value), fmt)
            except ValueError:
                continue
        raise ValidationError("Invalid date format. Use YYYY-MM-DD or DD/MM/YYYY.")


def validate_row(
    config, row_data: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Validates a complete row using the configured DSL fields and rules.
    Returns (cleaned_data, error_dict).
    """
    cleaned = {}
    errors = {}

    for f_name, f_config in config.fields.items():

        if isinstance(f_config, list):
            rules = f_config
        elif isinstance(f_config, dict):
            rules = list(f_config.get("rules", []))
            if f_config.get("required") and "required" not in rules:
                rules.insert(0, "required")
        else:
            rules = []

        val = row_data.get(f_name)
        validator = DSLValidator(f_name, rules, config)

        try:
            cleaned[f_name] = validator.validate(val, row_data)
        except ValidationError as e:
            errors[f_name] = e.messages[0]
        except Exception as e:

            logger.error(f"Validator Panic on field '{f_name}': {e}")
            errors[f_name] = "Incompatible data type for validation."

    return cleaned, errors
