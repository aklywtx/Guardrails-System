# src/guardrails/output/allergen.py

import re
from typing import List, Dict, Set
from src.guardrails.output.base import BaseValidator, ValidationError, ErrorSeverity

class AllergenValidator(BaseValidator):
    """
    Ensures LLM does not recommend containing an allergen to the user.
    """
    def __init__(self):
        # Define regex patterns for common "safe" claims.
        # Key: standard allergen name (must match menu data)
        # Value: list of regex patterns indicating ABSENCE of that allergen
        self.safe_claim_patterns = {
            'gluten': [r'gluten[\s-]*free', r'no\s+gluten', r'without\s+gluten', r'contains\s+no\s+gluten'],
            'peanuts': [r'peanut[\s-]*free', r'no\s+peanuts?', r'without\s+peanuts?', r'nut[\s-]*free'],
            'dairy': [r'dairy[\s-]*free', r'no\s+dairy', r'without\s+dairy', r'lactose[\s-]*free'],
            'shellfish': [r'shellfish[\s-]*free', r'no\s+shellfish', r'without\s+shellfish'],
            'eggs': [r'egg[\s-]*free', r'no\s+eggs?', r'without\s+eggs?'],
            'soy': [r'soy[\s-]*free', r'no\s+soy', r'without\s+soy'],
        }

    def validate(self, text: str, menu_index: Dict[str, Dict], user_constraints: Set[str] = None) -> List[ValidationError]:
        """
        Validate allergen safety.
        Checks two things:
        1. False claims (e.g., saying Pad Thai is peanut-free).
        2. Unsafe recommendations (mentioning a dish that violates user_constraints).
        """
        errors = []
        user_constraints = user_constraints or set()
        text_lower = text.lower()

        mentioned_dishes = []
        for dish_name_lower, dish_info in menu_index.items():
            if dish_name_lower in text_lower:
                mentioned_dishes.append(dish_info)

        if not mentioned_dishes:
            return []

        for dish in mentioned_dishes:
            actual_allergens = set(a.lower() for a in dish.get('allergens', []))

            # If user is allergic to X, and dish has X, do not mention it unless explicitly warning.
            # We just block any mention of unsafe dishes to be safe.
            violating_allergens = user_constraints.intersection(actual_allergens)
            if violating_allergens:
                errors.append(ValidationError(
                    error_type="unsafe_recommendation",
                    severity=ErrorSeverity.CRITICAL,
                    message=f"SAFETY BLOCK: User is allergic to {violating_allergens}, but response mentioned '{dish['name']}' which contains them.",
                    details={
                        "dish": dish['name'],
                        "violating_allergens": list(violating_allergens),
                        "user_constraints": list(user_constraints)
                    },
                    # TODO(later): Suggest a safer alternative
                ))
                continue # Skip to next dish if already blocked for this reason

            for allergen, patterns in self.safe_claim_patterns.items():
                # Only care if the dish actually ahas this allergen
                if allergen in actual_allergens:
                    for pattern in patterns:
                        if re.search(pattern, text_lower):
                            errors.append(ValidationError(
                                error_type="allergen_misinformation",
                                severity=ErrorSeverity.CRITICAL, # ALWAYS CRITICAL
                                message=f"SAFETY ALERT: '{dish['name']}' contains {allergen}, but response suggests it might be {allergen}-free.",
                                details={
                                    "dish": dish['name'],
                                    "allergen_found": allergen,
                                    "conflicting_segment": text.strip()
                                },
                                # No auto-fix for safety critical errors. Block it.
                                original_text=None, 
                                corrected_text=None
                            ))
                            break # Found one false claim for this allergen, no need to check other patterns

        return errors
