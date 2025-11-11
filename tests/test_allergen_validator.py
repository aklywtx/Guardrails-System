"""
Test cases for allergen safety validation guardrail.
Tests both unsafe recommendations and false safety claims.
"""

import pytest
from src.guardrails.output.allergen import AllergenValidator
from src.guardrails.output.base import ErrorSeverity
from src.guardrails.input.constraints import ConstraintExtractor
from src.menu_data import SAMPLE_MENU


@pytest.fixture
def validator():
    return AllergenValidator()


@pytest.fixture
def constraint_extractor():
    return ConstraintExtractor()


@pytest.fixture
def menu_index():
    """Build menu index from SAMPLE_MENU."""
    index = {}
    for category, items in SAMPLE_MENU.items():
        for item in items:
            index[item['name'].lower()] = item
    return index


class TestAllergenValidatorIsolation:
    """Test allergen validator in isolation with predefined constraints."""

    def test_safe_recommendation_passes(self, validator, menu_index):
        """Test that safe recommendations don't trigger errors."""
        text = "I recommend the Fruit Salad"
        user_constraints = {"peanuts"}  # User allergic to peanuts

        errors = validator.validate(text, menu_index, user_constraints)
        assert len(errors) == 0  # Fruit Salad has no allergens

    def test_unsafe_recommendation_blocked_critical(self, validator, menu_index):
        """
        CRITICAL TEST: Unsafe recommendation must be blocked.
        This is life-threatening for users.
        """
        text = "I highly recommend our Pad Thai!"
        user_constraints = {"peanuts"}  # User allergic to peanuts

        errors = validator.validate(text, menu_index, user_constraints)

        assert len(errors) == 1
        assert errors[0].error_type == "unsafe_recommendation"
        assert errors[0].severity == ErrorSeverity.CRITICAL
        assert "Pad Thai" in errors[0].message
        assert "peanuts" in str(errors[0].details).lower()

    def test_false_safety_claim_caught_critical(self, validator, menu_index):
        """
        CRITICAL TEST: False safety claims must be caught.
        LLM claiming a dish is allergen-free when it's not is dangerous.
        """
        text = "Our Pad Thai is peanut-free and delicious!"
        user_constraints = set()  # No user constraints, but false claim is still wrong

        errors = validator.validate(text, menu_index, user_constraints)

        assert len(errors) > 0
        assert errors[0].error_type == "allergen_misinformation"
        assert errors[0].severity == ErrorSeverity.CRITICAL
        assert "Pad Thai" in errors[0].message

    def test_multiple_allergens_all_checked(self, validator, menu_index):
        """Test that multiple user allergens are all validated."""
        text = "Try the Margherita Pizza or the Pad Thai"
        user_constraints = {"peanuts", "dairy"}  # Allergic to both

        errors = validator.validate(text, menu_index, user_constraints)

        # Both dishes should be flagged (Pizza has dairy, Pad Thai has peanuts)
        assert len(errors) == 2
        dish_names = [e.details['dish'] for e in errors]
        assert "Margherita Pizza" in dish_names
        assert "Pad Thai" in dish_names

    def test_shellfish_allergy_safety(self, validator, menu_index):
        """Test shellfish allergy protection (another common serious allergy)."""
        text = "Our Pad Thai is a customer favorite"
        user_constraints = {"shellfish"}

        errors = validator.validate(text, menu_index, user_constraints)

        assert len(errors) == 1  # Pad Thai contains shellfish
        assert errors[0].severity == ErrorSeverity.CRITICAL

    def test_no_constraints_no_errors(self, validator, menu_index):
        """Test that without constraints, valid recommendations pass."""
        text = "Try our Pad Thai or Margherita Pizza"
        user_constraints = set()

        errors = validator.validate(text, menu_index, user_constraints)
        # No false safety claims, so should pass
        assert len(errors) == 0

    def test_safe_and_unsafe_mixed(self, validator, menu_index):
        """Test response with both safe and unsafe recommendations."""
        text = "You could try the Fruit Salad or the Pad Thai"
        user_constraints = {"peanuts"}

        errors = validator.validate(text, menu_index, user_constraints)

        # Only Pad Thai should be flagged
        assert len(errors) == 1
        assert "Pad Thai" in errors[0].message

    def test_gluten_free_false_claim(self, validator, menu_index):
        """Test detection of false gluten-free claims."""
        text = "Our Margherita Pizza is gluten-free!"
        user_constraints = set()

        errors = validator.validate(text, menu_index, user_constraints)

        assert len(errors) > 0  # Pizza contains gluten
        assert "gluten" in errors[0].message.lower()


class TestAllergenValidatorFullFlow:
    """Test allergen validator integrated with constraint extraction."""

    def test_full_flow_allergy_stated_then_unsafe_rec(
        self, validator, constraint_extractor, menu_index
    ):
        """
        Full conversation flow test:
        1. User states allergy
        2. ConstraintExtractor extracts it
        3. AllergenValidator blocks unsafe recommendation
        """
        # Step 1: User states allergy
        user_input = "I'm allergic to peanuts"
        constraints = constraint_extractor.extract(user_input, set())

        assert "peanuts" in constraints

        # Step 2: LLM makes unsafe recommendation
        llm_response = "I recommend our Pad Thai"

        # Step 3: Validator blocks it
        errors = validator.validate(llm_response, menu_index, constraints)

        assert len(errors) == 1
        assert errors[0].severity == ErrorSeverity.CRITICAL

    def test_full_flow_safe_recommendation(
        self, validator, constraint_extractor, menu_index
    ):
        """Test that safe recommendations work in full flow."""
        # User states allergy
        user_input = "I can't eat dairy"
        constraints = constraint_extractor.extract(user_input, set())

        assert "dairy" in constraints

        # LLM recommends safe option
        llm_response = "Try our Fruit Salad, it's dairy-free"

        # Should pass validation
        errors = validator.validate(llm_response, menu_index, constraints)
        assert len(errors) == 0

    def test_full_flow_cumulative_constraints(
        self, validator, constraint_extractor, menu_index
    ):
        """Test that constraints accumulate across conversation."""
        constraints = set()

        # Turn 1: User mentions peanut allergy
        constraints = constraint_extractor.extract("allergic to peanuts", constraints)
        assert "peanuts" in constraints

        # Turn 2: User mentions dairy intolerance
        constraints = constraint_extractor.extract("no dairy please", constraints)
        assert "peanuts" in constraints
        assert "dairy" in constraints

        # Turn 3: LLM recommends something with dairy
        llm_response = "Try the Margherita Pizza"  # Has dairy
        errors = validator.validate(llm_response, menu_index, constraints)

        assert len(errors) == 1
        assert "dairy" in str(errors[0].details).lower()


class TestAllergenValidatorEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_response(self, validator, menu_index):
        """Test with empty LLM response."""
        errors = validator.validate("", menu_index, {"peanuts"})
        assert len(errors) == 0

    def test_no_dishes_mentioned(self, validator, menu_index):
        """Test response that doesn't mention any dishes."""
        text = "We have many options available for you!"
        errors = validator.validate(text, menu_index, {"peanuts"})
        assert len(errors) == 0

    def test_case_insensitive_allergen_matching(self, validator, menu_index):
        """Test that allergen matching is case-insensitive."""
        text = "Try our PAD THAI"  # Uppercase
        user_constraints = {"peanuts"}

        errors = validator.validate(text, menu_index, user_constraints)
        assert len(errors) == 1
