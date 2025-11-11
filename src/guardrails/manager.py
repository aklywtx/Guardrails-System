from typing import Dict, Optional, Set
from dataclasses import dataclass

# Input Guardrails
from .input.off_topic import OffTopicDetector
from .input.constraints import ConstraintExtractor

# Output Guardrails
from .output.base import ValidationResult, ErrorSeverity
from .output.price import PriceValidator
from .output.allergen import AllergenValidator

# Logging
from .logger import get_logger

@dataclass
class GuardrailInputResult:
    """Standardized result from input guardrail checks."""
    is_blocked: bool
    block_reason: Optional[str] = None
    topic_status: str = "unknown"
    similarity_score: float = 0.0

class GuardrailManager:
    """
    Central manager for all restaurant chatbot guardrails.
    Orchestrates Off-Topic, Constraints, Price, and Allergen checks.
    """

    def __init__(self, menu: Dict):
        print("Initializing Guardrail Manager...")
        # 1. Input Guardrails
        self.off_topic_detector = OffTopicDetector()
        self.constraint_extractor = ConstraintExtractor()

        # 2. Output Guardrails (Directly managing them now)
        self.price_validator = PriceValidator()
        self.allergen_validator = AllergenValidator()

        # 3. Build fast menu index once for all validators
        self.menu_index = self._build_menu_index(menu)

        # 4. Session State
        self._sessions: Dict[str, Dict] = {}

        # 5. Logger
        self.logger = get_logger()
        print("Guardrails ready.")

    def _build_menu_index(self, menu: Dict) -> Dict[str, Dict]:
        """Helper to flatten menu for O(1) lookups by validators."""
        index = {}
        for category, items in menu.items():
            for item in items:
                index[item['name'].lower()] = item
        return index

    def _get_session_constraints(self, session_id: str) -> Set[str]:
        if session_id not in self._sessions:
            self._sessions[session_id] = {"constraints": set()}
        return self._sessions[session_id]["constraints"]

    def _update_session_constraints(self, session_id: str, new_constraints: Set[str]):
        if session_id not in self._sessions:
            self._sessions[session_id] = {"constraints": set()}
        self._sessions[session_id]["constraints"] = new_constraints

    def check_input(self, prompt: str, session_id: str = "default") -> GuardrailInputResult:
        # 1. Off-Topic Detection
        topic_status, score = self.off_topic_detector.detect(prompt)
        if topic_status == "off_topic":
            # Log the block
            self.logger.log_input_block(topic_status, score, prompt, session_id)
            return GuardrailInputResult(True, "off_topic", topic_status, score)

        # 2. Constraint Extraction
        current = self._get_session_constraints(session_id)
        updated = self.constraint_extractor.extract(prompt, current)
        if updated != current:
            self._update_session_constraints(session_id, updated)

        return GuardrailInputResult(False, topic_status=topic_status, similarity_score=score)

    def check_output(self, llm_response: str, session_id: str = "default") -> ValidationResult:
        """
        Run all output validators sequentially and aggregate errors.
        """
        user_constraints = self._get_session_constraints(session_id)
        all_errors = []

        # Run Price Validator
        all_errors.extend(
            self.price_validator.validate(llm_response, self.menu_index)
        )

        # Run Allergen Validator (needs constraints)
        all_errors.extend(
            self.allergen_validator.validate(llm_response, self.menu_index, user_constraints)
        )

        # Log errors
        for error in all_errors:
            if error.severity == ErrorSeverity.CRITICAL:
                self.logger.log_critical_block(
                    error_type=error.error_type,
                    message=error.message,
                    details=error.details,
                    session_id=session_id
                )
            else:
                self.logger.log_output_error(
                    error_type=error.error_type,
                    severity=error.severity.value,
                    message=error.message,
                    details=error.details,
                    session_id=session_id,
                    response_preview=llm_response
                )

        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors
        )

    def reset_session(self, session_id: str = "default"):
        if session_id in self._sessions:
            del self._sessions[session_id]