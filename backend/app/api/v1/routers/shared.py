"""
Shared helpers and constants for QueueLess API routers.

- Redis cache client (sync, for get/set only)
- _cache_get / _cache_set / _cache_delete helpers
- Cache key constants
"""
import json

import redis as redis_sync

from app.core.config import get_settings

_settings = get_settings()

try:
    _redis = redis_sync.from_url(_settings.redis_url, decode_responses=True)
except Exception:
    _redis = None  # gracefully degrade if Redis unavailable

_CACHE_TTL = 45  # seconds
_ORG_LIST_KEY = "cache:orgs:list"
_ORG_SVC_KEY = "cache:org:{org_id}:services"


def _cache_get(key: str):
    try:
        if _redis:
            raw = _redis.get(key)
            if raw:
                return json.loads(raw)
    except Exception:
        pass
    return None


def _cache_set(key: str, value, ttl: int = _CACHE_TTL):
    try:
        if _redis:
            _redis.setex(key, ttl, json.dumps(value))
    except Exception:
        pass


def _cache_delete(*keys: str):
    try:
        if _redis and keys:
            _redis.delete(*keys)
    except Exception:
        pass
