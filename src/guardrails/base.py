from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
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

class BaseValidator(ABC):
    """Abstract base class for all output validators."""
    
    @abstractmethod
    def validate(self, text: str, menu_index: Dict[str, Dict]) -> List[ValidationError]:
        """
        Validate the text against the menu index.
        Must return a list of ValidationErrors (empty if valid).
        """
        pass