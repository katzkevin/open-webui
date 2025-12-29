# Wolvia Memory Injection with Caching

## Overview

Re-implement the Wolvia persistent memory injection feature that was previously reverted (commit `b2913fbd0`) due to latency issues. The new implementation uses namespace-based caching to eliminate the latency problem.

**Note:** Current `persistent-memory` is shared org-wide (`user_id=NULL` in Supabase). All users get the same content, so we use a single cache entry per namespace rather than per-user. See `wolvia/claude-todos/memory-namespace-architecture.md` for the full schema design.

## Background

### Original Implementation (Reverted)
- Added in commit `39b6da5de` (Nov 26, 2025)
- Reverted in commit `b2913fbd0` (Dec 2, 2025)
- Problem: Supabase API call added latency to every chat completion request

### Why Inject on Every Message?
The system message gets **re-processed** on each request via `apply_system_prompt_to_body(replace=True)` in `process_chat_payload()`. This means injected context from message 1 could be wiped on message 2. Therefore, we must inject on every message, not just the first.

## Implementation Plan

### 1. Add Environment Variables

**File:** `backend/open_webui/env.py`

```python
####################################
# WOLVIA
####################################

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
```

### 2. Add Cached Memory Fetch Function

**File:** `backend/open_webui/utils/middleware.py`

```python
from aiocache import cached

@cached(ttl=300, key="wolvia_persistent_memory_default")
async def fetch_wolvia_memory() -> str:
    """Fetch shared persistent-memory from Supabase (5 min TTL).

    Fetches org-wide memory where user_id IS NULL. Single cache entry
    since all users receive the same content.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return ""

    async with aiohttp.ClientSession(trust_env=True) as session:
        async with session.get(
            f"{SUPABASE_URL}/rest/v1/memories",
            params={
                "slug": "eq.persistent-memory",
                "namespace": "eq.default",
                "user_id": "is.null",  # Shared org-wide memory
                "select": "text",
            },
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            },
            timeout=aiohttp.ClientTimeout(total=5),
        ) as response:
            if response.status != 200:
                log.error(f"Supabase API returned status {response.status}")
                return ""
            data = await response.json()
            return data[0].get("text", "") if data else ""
```

### 3. Add Memory Handler Function

**File:** `backend/open_webui/utils/middleware.py`

```python
async def wolvia_memory_handler(
    request: Request, form_data: dict, extra_params: dict, user
) -> dict:
    """Inject Wolvia memory into system message on every request."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return form_data  # Skip if not configured (graceful, no crash)

    try:
        memory_text = await fetch_wolvia_memory()  # Shared memory, no user param
        if memory_text:
            form_data["messages"] = add_or_update_system_message(
                f"User Context from Wolvia:\n{memory_text}\n",
                form_data["messages"],
                append=True
            )
    except Exception as e:
        log.error(f"Wolvia memory fetch error: {e}")

    return form_data
```

### 4. Integrate into Request Pipeline

**File:** `backend/open_webui/utils/middleware.py`

In `process_chat_payload()`, add the handler call after pipeline inlet processing:

```python
# WOLVIA: Inject Wolvia memories
form_data = await wolvia_memory_handler(request, form_data, extra_params, user)
```

### 5. Add Imports

**File:** `backend/open_webui/utils/middleware.py`

Ensure these imports exist:
```python
import aiohttp
from aiocache import cached
from open_webui.env import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Cache strategy | `aiocache` in-memory | Already used in codebase, simple, fast |
| Cache TTL | 300 seconds (5 min) | Balance between freshness and performance |
| Cache key | Per-namespace (single entry) | Content is shared (`user_id=NULL`), all users get same memory |
| Query filter | `user_id=is.null` | Explicitly fetch shared org-wide memory |
| Missing config | Graceful skip | Don't crash if Supabase not configured |
| Injection timing | Every message | System message gets replaced on each request |
| Namespace | `default` | Production namespace (vs `test`) |

## Performance Characteristics

| Scenario | Latency |
|----------|---------|
| First request (cache miss) | ~100-500ms (Supabase API call) |
| Subsequent requests (cache hit) | <1ms (memory lookup) |
| After TTL expires | ~100-500ms (refresh) |

Since memory is shared (single cache entry), any user's request warms the cache for all users.

## Future Considerations

1. **Per-user memories**: Add separate function with user-specific cache key:
   ```python
   @cached(ttl=300, key=lambda user_id, slug: f"wolvia_{slug}_{user_id}")
   async def fetch_user_memory(user_id: str, slug: str) -> str:
       # Query: user_id=eq.{user_id}, namespace=default
       ...
   ```
2. **Multi-org support**: When adding `org_id` column, update cache key to include it
3. **Cache invalidation**: Could add endpoint to force-refresh cache if needed
4. **Redis backend**: If multi-instance deployment needed, switch aiocache to Redis backend:
   ```python
   from aiocache import Cache
   cache = Cache(Cache.REDIS, endpoint="...", port=6379)
   ```

## Testing

1. Verify memory injection appears in system message
2. Verify cache hit (second request from any user should not call Supabase)
3. Verify TTL expiry triggers refresh
4. Verify graceful handling when Supabase not configured
5. Verify graceful handling when Supabase returns error/empty
6. Verify `user_id=is.null` filter correctly fetches shared memory
