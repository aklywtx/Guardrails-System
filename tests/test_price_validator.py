"""
Test cases for price validation guardrail.
Tests that the validator catches price hallucinations and inaccuracies.
"""

import pytest
from src.guardrails.output.price import PriceValidator
from src.guardrails.output.base import ErrorSeverity
from src.menu_data import SAMPLE_MENU


@pytest.fixture
def validator():
    return PriceValidator()


@pytest.fixture
def menu_index():
    """Build menu index from SAMPLE_MENU."""
    index = {}
    for category, items in SAMPLE_MENU.items():
        for item in items:
            index[item['name'].lower()] = item
    return index


class TestPriceValidator:
    """Unit tests for price validation logic."""

    def test_correct_price_passes(self, validator, menu_index):
        """Test that correct prices don't trigger validation errors."""
        text = "The Coca-Cola is $2.99"
        errors = validator.validate(text, menu_index)
        assert len(errors) == 0

    def test_incorrect_price_caught(self, validator, menu_index):
        """Test that incorrect prices are caught and flagged."""
        text = "The Coca-Cola costs $4.99"  # Wrong: should be $2.99
        errors = validator.validate(text, menu_index)

        assert len(errors) == 1
        assert errors[0].error_type == "incorrect_price"
        assert errors[0].severity == ErrorSeverity.HIGH
        assert "Coca-Cola" in errors[0].message
        assert errors[0].details['stated_price'] == 4.99
        assert errors[0].details['actual_price'] == 2.99

    def test_price_without_dollar_sign(self, validator, menu_index):
        """Test that prices work with or without $ symbol."""
        text = "Coffee is 2.49"  # No $ sign
        errors = validator.validate(text, menu_index)
        assert len(errors) == 0

    def test_multiple_prices_in_response(self, validator, menu_index):
        """Test validation with multiple dishes and prices."""
        text = """We have several drinks: Coca-Cola for $2.99,
                  Orange Juice for $4.50, and Coffee for $2.49"""
        errors = validator.validate(text, menu_index)

        # Orange Juice should be flagged (actual: $3.99, stated: $4.50)
        assert len(errors) == 1
        assert "Orange Juice" in errors[0].message

    def test_dish_mentioned_without_price(self, validator, menu_index):
        """Test that mentioning a dish without price doesn't cause false positives."""
        text = "We have Coca-Cola available today"
        errors = validator.validate(text, menu_index)
        assert len(errors) == 0

    def test_auto_correction_provided(self, validator, menu_index):
        """Test that validator provides correction text for auto-fix."""
        text = "Coca-Cola is $5.00"
        errors = validator.validate(text, menu_index)

        assert len(errors) == 1
        assert errors[0].original_text is not None
        assert errors[0].corrected_text is not None
        assert "2.99" in errors[0].corrected_text

    def test_real_hallucination_case(self, validator, menu_index):
        """
        Test the real hallucination discovered during development.
        Reference: reflection.md lines 69-99

        LLM claimed Spaghetti Carbonara ($13.49) was cheapest,
        when Vegetable Curry ($11.99) is actually cheaper.
        """
        # This tests that validator catches price inaccuracies
        text = "Our Spaghetti Carbonara is affordable at $15.00"  # Wrong price
        errors = validator.validate(text, menu_index)

        assert len(errors) == 1
        assert "Spaghetti Carbonara" in errors[0].message
        assert errors[0].details['actual_price'] == 13.49


class TestPriceValidatorEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_text(self, validator, menu_index):
        """Test with empty string."""
        errors = validator.validate("", menu_index)
        assert len(errors) == 0

    def test_no_menu_items_mentioned(self, validator, menu_index):
        """Test text that doesn't mention any menu items."""
        text = "We have great food and excellent service!"
        errors = validator.validate(text, menu_index)
        assert len(errors) == 0

    def test_case_insensitive_matching(self, validator, menu_index):
        """Test that dish name matching is case-insensitive."""
        text = "COCA-COLA is $5.00"  # Wrong price, uppercase name
        errors = validator.validate(text, menu_index)
        assert len(errors) == 1
        assert "Coca-Cola" in errors[0].message
