"""
Test cases for constraint extraction (allergy/dietary restriction tracking).
Simple keyword-based extraction.
"""

import pytest
from src.guardrails.input.constraints import ConstraintExtractor


@pytest.fixture
def extractor():
    return ConstraintExtractor()


class TestConstraintExtractor:
    """Test constraint extraction from user input."""

    def test_extract_peanut_allergy(self, extractor):
        """Test extraction of peanut allergy."""
        text = "I'm allergic to peanuts"
        constraints = extractor.extract(text, set())
        assert "peanuts" in constraints

    def test_extract_multiple_allergens(self, extractor):
        """Test extraction of multiple allergens from one statement."""
        text = "I'm allergic to peanuts and shellfish"
        constraints = extractor.extract(text, set())
        assert "peanuts" in constraints
        assert "shellfish" in constraints

    def test_synonym_mapping_milk_to_dairy(self, extractor):
        """Test that 'milk' is mapped to 'dairy'."""
        text = "I can't have milk"
        constraints = extractor.extract(text, set())
        assert "dairy" in constraints

    def test_synonym_mapping_cheese_to_dairy(self, extractor):
        """Test that 'cheese' is mapped to 'dairy'."""
        text = "no cheese please"
        constraints = extractor.extract(text, set())
        assert "dairy" in constraints

    def test_cumulative_constraints(self, extractor):
        """Test that constraints accumulate over multiple calls."""
        constraints = set()

        # First extraction
        constraints = extractor.extract("allergic to peanuts", constraints)
        assert "peanuts" in constraints

        # Second extraction - should keep previous
        constraints = extractor.extract("also no dairy", constraints)
        assert "peanuts" in constraints
        assert "dairy" in constraints

    def test_case_insensitive_extraction(self, extractor):
        """Test that extraction works regardless of case."""
        text = "I'm allergic to GLUTEN"
        constraints = extractor.extract(text, set())
        assert "gluten" in constraints

    def test_no_allergens_mentioned(self, extractor):
        """Test that irrelevant text doesn't extract false positives."""
        text = "I'd like to see the menu please"
        constraints = extractor.extract(text, set())
        assert len(constraints) == 0

    def test_punctuation_handling(self, extractor):
        """Test that punctuation doesn't break extraction."""
        text = "I'm allergic to peanuts, eggs, and dairy."
        constraints = extractor.extract(text, set())
        assert "peanuts" in constraints
        assert "eggs" in constraints
        assert "dairy" in constraints


class TestConstraintExtractorEdgeCases:
    """Edge cases for constraint extraction."""

    def test_empty_string(self, extractor):
        """Test with empty input."""
        constraints = extractor.extract("", set())
        assert len(constraints) == 0

    def test_single_allergen_word(self, extractor):
        """Test with just the allergen word."""
        text = "peanuts"
        constraints = extractor.extract(text, set())
        assert "peanuts" in constraints

    def test_does_not_overwrite_existing(self, extractor):
        """Test that existing constraints are preserved."""
        existing = {"gluten", "soy"}
        text = "I'm also allergic to peanuts"

        constraints = extractor.extract(text, existing)

        assert "gluten" in constraints
        assert "soy" in constraints
        assert "peanuts" in constraints
