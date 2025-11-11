from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

class ErrorSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"

@dataclass
class ValidationError:
    error_type: str
    severity: ErrorSeverity
    message: str
    details: Dict[str, Any]
    original_text: Optional[str] = None
    corrected_text: Optional[str] = None

@dataclass
class ValidationResult:
    """Standardized result from output validation."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    
    @property
    def critical_errors(self) -> List[ValidationError]:
        return [e for e in self.errors if e.severity == ErrorSeverity.CRITICAL]

class BaseValidator(ABC):
    """Abstract base class for all output validators."""
    
    @abstractmethod
    def validate(self, text: str, menu_index: Dict[str, Dict], user_constraints: Optional[Set[str]] = None) -> List[ValidationError]:
        """
        Validate the text against the menu index.
        Must return a list of ValidationErrors (empty if valid).
        """
        pass