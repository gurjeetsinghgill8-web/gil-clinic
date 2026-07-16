"""Repository implementations for the Identity Engine.

All repositories follow the same pattern:
1. Accept domain entity, map to SQLAlchemy model
2. Use Specification pattern for filtering
3. Support OCC via version field
4. Support batch operations
5. Support pagination + cursor pagination
6. No business logic — only persistence
"""
