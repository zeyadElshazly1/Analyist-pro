"""
Redis-backed analysis result cache.

Cache key: analysis:{project_id}:{file_hash}
TTL:       CACHE_TTL_SECONDS (default 3600 = 1 hour)

If Redis is unavailable or REDIS_URL is unset, every operation degrades
silently — the platform works without caching, just without the speedup.
"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Module-level singleton — created once on first use
_redis_client: Any = None
_redis_available: bool | None = None  # None = not yet probed


def _get_redis():
    global _redis_client, _redis_available
    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client

    try:
        import redis as _redis
        from app.config import REDIS_URL
        if not REDIS_URL:
            _redis_available = False
            return None
        client = _redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        _redis_client = client
        _redis_available = True
        logger.info("Redis analysis cache connected")
    except Exception as e:
        logger.warning(f"Redis cache unavailable — running without cache: {e}")
        _redis_available = False

    return _redis_client


def _cache_key(project_id: int, file_hash: str) -> str:
    return f"analysis:{project_id}:{file_hash}"


def get_cached_analysis(project_id: int, file_hash: str | None) -> dict | None:
    """Return cached analysis result, or None on miss / unavailability."""
    if not file_hash:
        return None
    try:
        r = _get_redis()
        if r is None:
            return None
        raw = r.get(_cache_key(project_id, file_hash))
        if raw:
            logger.debug(f"Cache HIT project={project_id} hash={file_hash[:8]}…")
            return json.loads(raw)
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
    return None


def set_cached_analysis(project_id: int, file_hash: str | None, result: dict) -> None:
    """Write analysis result to cache with configured TTL."""
    if not file_hash:
        return
    try:
        r = _get_redis()
        if r is None:
            return
        from app.config import CACHE_TTL_SECONDS
        serialized = json.dumps(result, default=str)
        r.setex(_cache_key(project_id, file_hash), CACHE_TTL_SECONDS, serialized)
        logger.debug(
            f"Cache SET project={project_id} hash={file_hash[:8]}… "
            f"size={len(serialized)} TTL={CACHE_TTL_SECONDS}s"
        )
    except Exception as e:
        logger.warning(f"Cache write error: {e}")


def invalidate_project_cache(project_id: int, file_hash: str | None) -> None:
    """Evict the cached result for a project (call when a new file is uploaded)."""
    if not file_hash:
        return
    try:
        r = _get_redis()
        if r is None:
            return
        deleted = r.delete(_cache_key(project_id, file_hash))
        if deleted:
            logger.debug(f"Cache INVALIDATED project={project_id}")
    except Exception as e:
        logger.warning(f"Cache invalidation error: {e}")
