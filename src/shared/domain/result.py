"""Result type for error handling without exceptions.

Inspired by Rust's Result type — returns either Ok(value) or Error(detail).
Eliminates try/except for expected failure modes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

TOk = TypeVar("TOk")
TErr = TypeVar("TErr")


@dataclass(frozen=True)
class Ok(Generic[TOk]):
    """Success result wrapper."""

    value: TOk


@dataclass(frozen=True)
class Error(Generic[TErr]):
    """Failure result wrapper."""

    detail: TErr


Result = Ok[TOk] | Error[TErr]
"""Union type representing either success (Ok) or failure (Error).

Usage:
    def divide(a: int, b: int) -> Result[int, str]:
        if b == 0:
            return Error("division by zero")
        return Ok(a // b)

    result = divide(10, 2)
    match result:
        case Ok(value):
            print(f"Result: {value}")
        case Error(detail):
            print(f"Error: {detail}")
"""
