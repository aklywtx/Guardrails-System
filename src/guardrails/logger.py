"""
Simple JSON logger for guardrail events.
Logs all validation errors and blocks to logs/guardrails.log
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class GuardrailLogger:
    """Simple JSON logger for tracking guardrail events."""

    def __init__(self, log_file: str = "logs/guardrails.log"):
        self.log_file = log_file
        self._ensure_log_directory()

    def _ensure_log_directory(self):
        """Create logs directory if it doesn't exist."""
        log_dir = Path(self.log_file).parent
        log_dir.mkdir(exist_ok=True)

    def _write_log(self, event: Dict[str, Any]):
        """Write a JSON event to the log file."""
        event["timestamp"] = datetime.now().isoformat()

        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            # Don't crash the application if logging fails
            print(f"Warning: Failed to write to log: {e}")

    def log_input_block(
        self,
        topic_status: str,
        similarity_score: float,
        query: str,
        session_id: str
    ):
        """Log when input is blocked by input guardrails."""
        self._write_log({
            "type": "INPUT_BLOCKED",
            "topic_status": topic_status,
            "similarity_score": round(similarity_score, 4),
            "query": query[:100],  # Truncate long queries
            "session_id": session_id
        })

    def log_output_error(
        self,
        error_type: str,
        severity: str,
        message: str,
        details: Dict[str, Any],
        session_id: str,
        response_preview: Optional[str] = None
    ):
        """Log when output validation catches an error."""
        log_entry = {
            "type": "OUTPUT_ERROR",
            "error_type": error_type,
            "severity": severity,
            "message": message,
            "details": details,
            "session_id": session_id
        }

        if response_preview:
            log_entry["response_preview"] = response_preview[:100]

        self._write_log(log_entry)

    def log_critical_block(
        self,
        error_type: str,
        message: str,
        details: Dict[str, Any],
        session_id: str
    ):
        """Log critical safety blocks (allergen conflicts, etc.)."""
        self._write_log({
            "type": "CRITICAL_BLOCK",
            "error_type": error_type,
            "severity": "CRITICAL",
            "message": message,
            "details": details,
            "session_id": session_id
        })


# Global logger instance
_logger = None

def get_logger() -> GuardrailLogger:
    """Get or create the global logger instance."""
    global _logger
    if _logger is None:
        _logger = GuardrailLogger()
    return _logger
