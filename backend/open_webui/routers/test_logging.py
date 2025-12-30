"""
Test endpoint for validating Datadog and Sentry integration.
This endpoint should only be available in dev environments.
"""
import logging
from typing import Optional

import sentry_sdk
from fastapi import APIRouter, Depends, HTTPException, Query
from open_webui.utils.auth import get_admin_user

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/test-logging")
async def test_logging(user=Depends(get_admin_user)):
    """
    Test endpoint for Datadog and Sentry integration.

    This endpoint:
    1. Logs a warning message
    2. Logs an error message
    3. Raises an exception (caught by Sentry)

    Only accessible to admin users.
    """
    # Log a warning
    log.warning("Test warning log from test-logging endpoint")

    # Log an error (message doesn't contain "ERROR" to verify level detection)
    log.error("Test critical log from test-logging endpoint")

    # Raise an exception to test Sentry integration
    raise HTTPException(
        status_code=500,
        detail="Test exception from test-logging endpoint - this is intentional for testing Datadog and Sentry integration"
    )


@router.get("/test-sentry")
async def test_sentry(testId: Optional[str] = Query(None, description="Test ID for tracking in Sentry")):
    """
    Test endpoint for Sentry integration verification.

    Used by scripts/sentry_verify.py to confirm errors reach Sentry.
    Captures a test error with the provided testId for easy lookup.

    No authentication required for easy automated testing.
    """
    test_id = testId or "no-test-id"

    # Log the test attempt
    log.info(f"Sentry test triggered with testId: {test_id}")

    # Capture a real ValueError in Sentry (not a custom test exception)
    try:
        raise ValueError(f"Sentry test error - testId: {test_id}")
    except ValueError as e:
        sentry_sdk.capture_exception(e)
        log.error(f"Sentry test error captured - testId: {test_id}")

    return {"status": "error_captured", "testId": test_id, "message": "Test error sent to Sentry"}
