"""Domain policies for the Identity Engine.

Policies encapsulate business rules that don't naturally belong in
a single entity or value object. They coordinate across multiple
aggregates and enforce invariants.

Available policies:
- LockoutPolicy: Account lockout rules (max attempts, lock duration)
- SessionPolicy: Session lifecycle rules (max sessions, expiry)
"""

from src.domain.identity.policies.lockout_policy import LockoutPolicy
from src.domain.identity.policies.session_policy import SessionPolicy

__all__ = [
    "LockoutPolicy",
    "SessionPolicy",
]
