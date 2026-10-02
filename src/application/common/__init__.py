"""Application common layer — shared base classes for all engines.

Provides reusable patterns that every engine (Identity, Patient, Queue, Billing, etc.)
uses in its application layer:

- BaseUseCase: Abstract base with UoW, event collection, audit hook
- Command / Query: CQRS markers
- CommandHandler / QueryHandler: Handler interfaces
- BaseValidator: Input validation base
- ApplicationException: Typed app-level errors
- Result: Success/failure result type
- Pagination: Offset/limit pagination
- TransactionManager: UoW commit abstraction
"""

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command, Query
from src.application.common.handler import CommandHandler, QueryHandler
from src.application.common.validator import BaseValidator
from src.application.common.exceptions import ApplicationException
from src.application.common.result import Result
from src.application.common.pagination import Pagination
from src.application.common.transaction import TransactionManager

__all__ = [
    "BaseUseCase",
    "Command",
    "Query",
    "CommandHandler",
    "QueryHandler",
    "BaseValidator",
    "ApplicationException",
    "Result",
    "Pagination",
    "TransactionManager",
]
