"""Redis client for pub/sub and caching.

Provides:
- Connection management with env-var configuration
- Pub/sub channels for event bus
- Cache utilities
- Health check
"""

from __future__ import annotations

import json
import os
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis


def get_redis_url() -> str:
    """Get Redis URL from environment variable.

    Returns:
        Redis URL string. Defaults to local Redis.
    """
    return os.getenv(
        "GHOS_REDIS_URL",
        "redis://:ghos@localhost:6379/0",
    )


_redis_client: Redis | None = None


async def get_redis() -> Redis:
    """Get or create the Redis connection.

    Returns:
        Configured Redis client instance.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            get_redis_url(),
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection gracefully."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


async def publish_event(channel: str, event: dict[str, Any]) -> None:
    """Publish an event to a Redis pub/sub channel.

    Args:
        channel: Channel name (e.g. "identity:events").
        event: Event payload dict (serialized as JSON).
    """
    redis = await get_redis()
    await redis.publish(channel, json.dumps(event, default=str))


async def check_redis_health() -> bool:
    """Check if Redis is reachable.

    Returns:
        True if Redis responds, False otherwise.
    """
    try:
        redis = await get_redis()
        await redis.ping()
        return True
    except Exception:
        return False
