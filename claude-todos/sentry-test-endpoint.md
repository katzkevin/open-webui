# Add Sentry Test Endpoint

**Priority:** High  
**Context:** Wolvia Sentry verification system needs this endpoint to verify errors reach Sentry.

## Task

Add `/api/test-sentry` endpoint that triggers a test error for Sentry verification.

## Implementation

Location: Likely in `backend/open_webui/apps/webui/routers/` or similar

```python
from fastapi import APIRouter, Query
import sentry_sdk
import uuid

router = APIRouter()

@router.get("/api/test-sentry")
def test_sentry(test_id: str = Query(default=None)):
    """Trigger a test error for Sentry verification.

    Used by: scripts/sentry_verify.py in wolvia repo
    Usage: GET /api/test-sentry?testId=<uuid>
    """
    test_id = test_id or str(uuid.uuid4())

    try:
        raise RuntimeError(f"Sentry test error: {test_id}")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return {"status": "error_captured", "test_id": test_id}
```

## Verification

After implementing, test with:
```bash
# From wolvia repo
just sentry-verify openwebui dev
```

## Related

- Wolvia repo: `scripts/sentry_verify.py` expects this endpoint
- Endpoint URL: `https://chat.{dev.,}wolvia.ai/api/test-sentry`
