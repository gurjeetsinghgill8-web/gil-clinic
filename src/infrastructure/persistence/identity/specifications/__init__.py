"""Specification pattern for reusable query filters.

Instead of repository methods like find_active_users() or find_locked_users(),
repositories accept Specification objects that encapsulate the filtering logic.

This keeps repositories generic and query logic reusable and testable.
"""
