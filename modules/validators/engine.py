import re
from typing import Any, List, Dict, Optional

class DynamicValidator:
    def validate_field(self, key: str, value: Any, rules: List[Dict], all_values: Dict) -> List[str]:
        errors = []
        for rule in rules:
            rule_type = rule.get("type")
            rule_val  = rule.get("value")
            msg       = rule.get("message")

            if rule_type == "required":
                if value is None or (isinstance(value, str) and not value.strip()):
                    errors.append(msg or f"{key} is required.")

            elif rule_type == "min_length":
                if isinstance(value, str) and len(value) < int(rule_val):
                    errors.append(msg or f"{key} must be at least {rule_val} characters.")

            elif rule_type == "max_length":
                if isinstance(value, str) and len(value) > int(rule_val):
                    errors.append(msg or f"{key} cannot exceed {rule_val} characters.")

            elif rule_type == "min":
                try:
                    if float(value) < float(rule_val):
                        errors.append(msg or f"{key} must be >= {rule_val}.")
                except (TypeError, ValueError): pass

            elif rule_type == "max":
                try:
                    if float(value) > float(rule_val):
                        errors.append(msg or f"{key} must be <= {rule_val}.")
                except (TypeError, ValueError): pass

            elif rule_type == "regex":
                if value and not re.fullmatch(rule_val, str(value)):
                    errors.append(msg or f"{key} format is invalid.")

            elif rule_type == "dependent_required":
                if self._evaluate_condition(rule["condition"], all_values):
                    if value is None or (isinstance(value, str) and not value.strip()):
                        errors.append(msg or f"{key} is required based on your other selections.")
        return errors

    def validate_submission(self, fields_meta: List[Dict], data: Dict) -> Dict[str, List[str]]:
        """Returns {field_key: [error_messages]} for all invalid fields."""
        all_errors = {}
        for field in fields_meta:
            key    = field["key"]
            value  = data.get(key)
            rules  = field.get("validation_rules", [])
            errors = self.validate_field(key, value, rules, data)
            if errors:
                all_errors[key] = errors
        return all_errors

    def _evaluate_condition(self, condition: Dict, all_values: Dict) -> bool:
        field_val = all_values.get(condition["field"])
        op        = condition.get("operator", "eq")
        cmp_val   = condition["value"]

        try:
            if op == "eq":      return str(field_val) == str(cmp_val)
            if op == "neq":     return str(field_val) != str(cmp_val)
            if op == "in":      return field_val in cmp_val
            if op == "gt":      return float(field_val or 0) > float(cmp_val)
            if op == "lt":      return float(field_val or 0) < float(cmp_val)
        except (TypeError, ValueError):
            return False
        return False
