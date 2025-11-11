from typing import Set
import re

class ConstraintExtractor:
    """
    Simple rule-based extractor for user allergen constraints.
    NOTE: This is an MVP implementation (cumulative only, no negations).
    """
    def __init__(self):
        # Supported allergens to look for (must match menu data keys usually)
        self.supported_allergens = {
            'gluten', 'peanuts', 'dairy', 'shellfish', 'eggs', 'soy', 'nuts'
        }
        # Mapping some common synonyms to standard keys
        self.synonyms = {
            'milk': 'dairy',
            'cheese': 'dairy',
            'peanut': 'peanuts',
            'nut': 'nuts',
            'egg': 'eggs'
        }

    def extract(self, text: str, current_constraints: Set[str]) -> Set[str]:
        """
        Update constraints based on user input.
        Returns a set of constraints.
        """
        text_lower = text.lower()
        new_constraints = current_constraints.copy()

        # Very simple keyword matching for MVP
        # Matches: "allergic to X", "allergy X", "no X" (simplified)
        for word in text_lower.replace('.', ' ').replace(',', ' ').split():
            # Check standard allergens
            if word in self.supported_allergens:
                new_constraints.add(word)
            # Check synonyms
            elif word in self.synonyms:
                new_constraints.add(self.synonyms[word])
        
        # A slightly better regex approach if you want to be a bit more precise:
        # re.search(r'(allergic|allergy|no)\s+(to\s+)?(peanuts|gluten|dairy...)', text_lower)
        # But simple keyword might be enough for MVP if you document limitations.
        
        return new_constraints
