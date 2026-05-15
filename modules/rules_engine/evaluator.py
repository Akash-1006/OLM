from typing import Any, Dict, List, Union

class RuleEvaluator:
    @staticmethod
    def evaluate(rule: Dict, all_values: Dict) -> bool:
        if not rule:
            return True

        operator = rule.get("operator")
        rules = rule.get("rules")

        if rules:
            # Compound rule
            results = [RuleEvaluator.evaluate(r, all_values) for r in rules]
            if operator == "AND":
                return all(results)
            elif operator == "OR":
                return any(results)
            return True

        # Leaf rule
        field = rule.get("field")
        op = rule.get("op")
        value = rule.get("value")

        field_val = all_values.get(field)

        try:
            if op == "eq":       return str(field_val) == str(value)
            if op == "neq":      return str(field_val) != str(value)
            if op == "gt":       return float(field_val) > float(value)
            if op == "gte":      return float(field_val) >= float(value)
            if op == "lt":       return float(field_val) < float(value)
            if op == "lte":      return float(field_val) <= float(value)
            if op == "in":       return isinstance(value, list) and field_val in value
            if op == "not_in":   return isinstance(value, list) and field_val not in value
            if op == "is_empty": return not field_val or field_val == ""
            if op == "is_not_empty": return bool(field_val) and field_val != ""
        except (TypeError, ValueError):
            return False

        return True
