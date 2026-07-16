"""Base entity with UUIDv7 primary key and timestamps.

All domain entities across all 13 engines inherit from this.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field


def uuid7() -> uuid.UUID:
    """Generate a time-sortable UUIDv7 value.

    UUIDv7 encodes a Unix ms timestamp in the most significant bits,
    making it index-friendly and naturally sortable by creation time.

    Format: tttttttt-tttt-7uuu-{variant}-uuuuuuuuuuuu
    """
    timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    # 48-bit timestamp
    time_high = (timestamp_ms >> 16) & 0xFFFFFFFF
    time_mid = timestamp_ms & 0xFFFF
    # Version 7
    time_hi_and_version = (time_mid & 0x0FFF) | (0x7 << 12)
    # Variant 10xx
    node = int.from_bytes(uuid.uuid4().bytes[2:8], "big")
    clock_seq = (node >> 62) & 0x3
    clock_seq_hi_and_reserved = (clock_seq & 0x3F) | 0x80
    clock_seq_low = node & 0xFF
    return uuid.UUID(
        fields=(
            time_high,
            time_mid,
            time_hi_and_version,
            clock_seq_hi_and_reserved,
            clock_seq_low,
            node & 0xFFFFFFFFFFFF,
        )
    )


@dataclass(kw_only=True)
class BaseEntity:
    """Base class for all domain entities.

    Provides:
    - UUIDv7 primary key
    - Created/updated timestamps
    - Version field for Optimistic Concurrency Control (OCC)
    - Equality by identity (id field)

    Every aggregate includes a version field for OCC.
    On every update: version = version + 1 with WHERE version = old_version.
    If no rows match, another transaction has modified the record concurrently.
    """

    id: uuid.UUID = field(default_factory=uuid7)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    version: int = 1

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseEntity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def touch(self) -> None:
        """Update the updated_at timestamp and increment version."""
        self.updated_at = datetime.now(timezone.utc)
        self.version += 1
