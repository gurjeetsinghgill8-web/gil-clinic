"""Base validator for use case input validation.

Every use case validates its input before executing business logic.
Validators run authorization checks + structural validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Result of a validation check.

    Attributes:
        is_valid: True if all checks passed.
        errors: Dict of field_name -> error_message for invalid fields.
    """

    is_valid: bool = True
    errors: dict[str, str] = field(default_factory=dict)

    def add_error(self, field: str, message: str) -> None:
        """Add a validation error.

        Args:
            field: The field name that failed validation.
            message: Human-readable error message.
        """
        self.errors[field] = message
        self.is_valid = False

    def add_errors(self, errors: dict[str, str]) -> None:
        """Add multiple validation errors.

        Args:
            errors: Dict of field_name -> error_message.
        """
        self.errors.update(errors)
        if errors:
            self.is_valid = False

    def raise_if_invalid(self) -> None:
        """Raise ValidationError if validation failed.

        Raises:
            ValidationError: With all field errors attached.
        """
        if not self.is_valid:
            from src.application.common.exceptions import ValidationError

            raise ValidationError(
                message="Input validation failed",
                details={"fields": self.errors},
            )

    def __repr__(self) -> str:
        if self.is_valid:
            return "<ValidationResult VALID>"
        return f"<ValidationResult INVALID errors={self.errors}>"


class BaseValidator:
    """Base class for all use case validators.

    Subclasses implement validate() and call add_error() for failures.

    Usage:
        class AuthValidator(BaseValidator):
            def validate(self, dto: LoginRequest) -> ValidationResult:
                result = ValidationResult()
                if not dto.username:
                    result.add_error("username", "Username is required")
                return result
    """

    def validate(self, dto: Any) -> ValidationResult:
        """Validate the input DTO.

        Args:
            dto: Input data transfer object.

        Returns:
            ValidationResult with is_valid and errors.
        """
        raise NotImplementedError("Subclasses must implement validate()")
