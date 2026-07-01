"""Domain-layer exception classes.

All domain exceptions inherit from DomainError (which extends Exception).
Domain layer uses only standard library — no framework imports.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base exception for all domain errors."""

    code: str = "ERR-DOMAIN-001"
    message: str = "Domain rule violation"

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details or {}
        if code:
            self.code = code
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class EntityNotFoundError(DomainError):
    """Raised when a domain entity is not found."""
    code: str = "ERR-DOMAIN-002"
    message: str = "Entity not found"

    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity_type} not found: {entity_id}",
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


class InvalidStateTransitionError(DomainError):
    """Raised when an invalid state transition is attempted."""
    code: str = "ERR-DOMAIN-003"
    message: str = "Invalid state transition"

    def __init__(self, entity_type: str, current_state: str, target_state: str) -> None:
        super().__init__(
            message=f"Cannot transition {entity_type} from {current_state} to {target_state}",
            details={
                "entity_type": entity_type,
                "current_state": current_state,
                "target_state": target_state,
            },
        )


class InvalidOperationError(DomainError):
    """Raised when an operation is invalid for the current entity state."""
    code: str = "ERR-DOMAIN-004"
    message: str = "Invalid operation"

    def __init__(self, operation: str, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=f"Cannot {operation}: {reason}",
            details={"operation": operation, "reason": reason, **(details or {})},
        )


class ValidationError(DomainError):
    """Raised when a domain value object validation fails."""
    code: str = "ERR-DOMAIN-005"
    message: str = "Validation failed"

    def __init__(self, field: str, reason: str | None = None, value: Any = None) -> None:
        if reason is None:
            # Single-arg mode: field is used as the full message
            super().__init__(
                message=field,
                details={"field": "", "reason": field, "value": str(value) if value is not None else None},
            )
        else:
            super().__init__(
                message=f"Validation failed for {field}: {reason}",
                details={"field": field, "reason": reason, "value": str(value) if value is not None else None},
            )


DomainValidationError = ValidationError


class InvalidQualityScoreError(DomainError):
    """Raised when a quality score value is out of the valid range."""
    code: str = "ERR-DOMAIN-006"
    message: str = "Invalid quality score"

    def __init__(self, score: float, reason: str = "Score must be between 0 and 100") -> None:
        super().__init__(
            message=f"Invalid quality score {score}: {reason}",
            details={"score": score, "reason": reason},
        )


class InvalidVideoFormatError(DomainError):
    """Raised when a video format is not supported."""
    code: str = "ERR-DOMAIN-007"
    message: str = "Unsupported video format"

    def __init__(self, format: str, supported_formats: list[str] | None = None) -> None:
        details = {"provided_format": format}
        if supported_formats:
            details["supported_formats"] = supported_formats
        super().__init__(
            message=f"Unsupported video format: {format}",
            details=details,
        )


class InvalidClipRangeError(DomainError):
    """Raised when a clip's time range is invalid."""
    code: str = "ERR-DOMAIN-008"
    message: str = "Invalid clip range"

    def __init__(self, start_ms: int, end_ms: int, reason: str = "Start must be before end") -> None:
        super().__init__(
            message=f"Invalid clip range ({start_ms}ms - {end_ms}ms): {reason}",
            details={"start_ms": start_ms, "end_ms": end_ms, "reason": reason},
        )


class InvalidExportStateError(DomainError):
    """Raised when an export state transition is invalid."""
    code: str = "ERR-DOMAIN-009"
    message: str = "Invalid export state"

    def __init__(self, current_state: str, target_state: str, reason: str | None = None) -> None:
        msg = f"Cannot transition export from {current_state} to {target_state}"
        if reason:
            msg += f": {reason}"
        super().__init__(
            message=msg,
            details={"current_state": current_state, "target_state": target_state, "reason": reason},
        )


class InvalidCaptionStateError(DomainError):
    """Raised when a caption operation is invalid for the current state."""
    code: str = "ERR-DOMAIN-010"
    message: str = "Invalid caption state"

    def __init__(self, operation: str, reason: str) -> None:
        super().__init__(
            message=f"Cannot {operation}: {reason}",
            details={"operation": operation, "reason": reason},
        )


class InvalidProviderStateError(DomainError):
    """Raised when a provider operation is invalid."""
    code: str = "ERR-DOMAIN-011"
    message: str = "Invalid provider state"

    def __init__(self, provider_id: str, operation: str, reason: str) -> None:
        super().__init__(
            message=f"Cannot {operation} for provider '{provider_id}': {reason}",
            details={"provider_id": provider_id, "operation": operation, "reason": reason},
        )


class InvalidPluginStateError(DomainError):
    """Raised when a plugin operation is invalid."""
    code: str = "ERR-DOMAIN-012"
    message: str = "Invalid plugin state"

    def __init__(self, plugin_name: str, operation: str, reason: str) -> None:
        super().__init__(
            message=f"Cannot {operation} for plugin '{plugin_name}': {reason}",
            details={"plugin_name": plugin_name, "operation": operation, "reason": reason},
        )


class InvalidAnalysisStateError(DomainError):
    """Raised when an analysis state transition is invalid."""
    code: str = "ERR-DOMAIN-013"
    message: str = "Invalid analysis state"

    def __init__(self, current_state: str, target_state: str, reason: str | None = None) -> None:
        msg = f"Cannot transition analysis from {current_state} to {target_state}"
        if reason:
            msg += f": {reason}"
        super().__init__(
            message=msg,
            details={"current_state": current_state, "target_state": target_state, "reason": reason},
        )


class InvalidProjectStateError(DomainError):
    """Raised when a project state transition is invalid."""
    code: str = "ERR-DOMAIN-014"
    message: str = "Invalid project state"

    def __init__(self, current_state: str, target_state: str, reason: str | None = None) -> None:
        msg = f"Cannot transition project from {current_state} to {target_state}"
        if reason:
            msg += f": {reason}"
        super().__init__(
            message=msg,
            details={"current_state": current_state, "target_state": target_state, "reason": reason},
        )


class InvalidTimestampError(DomainError):
    """Raised when a timestamp value is out of valid range."""
    code: str = "ERR-DOMAIN-015"
    message: str = "Invalid timestamp"

    def __init__(self, field: str, value: int, max_value: int | None = None) -> None:
        details = {"field": field, "value": value}
        if max_value is not None:
            details["max_value"] = max_value
        super().__init__(
            message=f"Invalid timestamp for {field}: {value}",
            details=details,
        )


class InvalidVideoStateError(DomainError):
    """Raised when a video state transition is invalid."""
    code: str = "ERR-DOMAIN-016"
    message: str = "Invalid video state"

    def __init__(self, current_state: str, target_state: str, reason: str | None = None) -> None:
        msg = f"Cannot transition video from {current_state} to {target_state}"
        if reason:
            msg += f": {reason}"
        super().__init__(
            message=msg,
            details={"current_state": current_state, "target_state": target_state, "reason": reason},
        )
