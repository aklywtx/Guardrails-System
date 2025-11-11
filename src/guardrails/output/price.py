import re
from typing import List, Dict, Set, Optional
from .base import BaseValidator, ValidationError, ErrorSeverity

class PriceValidator(BaseValidator):
    """
    Deterministic validator for menu item prices.
    Verifies that any price mentioned near a dish name matches the official menu price.
    Supports auto-correction by providing original and corrected text segments.
    """

    def validate(self, text: str, menu_index: Dict[str, Dict], user_constraints: Optional[Set[str]] = None) -> List[ValidationError]:
        """
        Validates prices in the text against the menu index.
        Ignores user_constraints as price accuracy is universal.
        """
        errors = []
        text_lower = text.lower()

        for dish_name_lower, dish_info in menu_index.items():
            if dish_name_lower not in text_lower:
                continue

            # 2. Construct regex for this dish.
            # It looks for:
            # - The exact dish name (case-insensitive)
            # - Followed by up to 50 characters that are NOT digits, '$', or newlines (fillers)
            # - Followed optionally by '$'
            # - Captures the price digits exactly (e.g., "12.99")
            pattern = re.compile(
                re.escape(dish_name_lower) + r"(?:[^$0-9\n]{0,50})\$?(\d+\.\d{2})",
                re.IGNORECASE
            )

            # 3. Find all occurrences of this dish followed by a price
            for match in pattern.finditer(text):
                full_match_text = match.group(0)   # e.g., "Pad Thai costs $10.50"
                stated_price_str = match.group(1)  # e.g., "10.50"
                
                stated_price = float(stated_price_str)
                actual_price = dish_info['price']
                print(stated_price, actual_price)
                # 4. Compare with a tiny epsilon for float safety
                if abs(stated_price - actual_price) > 0.001:
                    # If a mismatch is found, fix the wrong price
                    # We take the matched segment ("Pad Thai costs $10.50")
                    # and replace only the price part ("10.50" -> "13.99")
                    corrected_match_text = full_match_text.replace(
                        stated_price_str,
                        f"{actual_price:.2f}"
                    )

                    errors.append(ValidationError(
                        error_type="incorrect_price",
                        severity=ErrorSeverity.HIGH, # High because it's factual wrong, but usually not life-threatening
                        message=f"Incorrect price for '{dish_info['name']}': stated ${stated_price:.2f}, actual ${actual_price:.2f}",
                        details={
                            "dish": dish_info['name'],
                            "stated_price": stated_price,
                            "actual_price": actual_price
                        },
                        # These allow the main loop to perform str.replace() securely
                        original_text=full_match_text,
                        corrected_text=corrected_match_text
                    ))

        return errors